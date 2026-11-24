// 클사무관의 예산 프리즘 · AI분석 중계 서버 (Cloudflare Workers 무료 플랜)
// 역할: 브라우저에 API 키를 노출하지 않고, 허용된 사이트에서 온 질문만 LLM에 전달한다.
// 환경변수(Worker 설정 > Variables and Secrets):
//   GEMINI_API_KEY (필수, 기본 LLM 1번), GROQ_API_KEY (2번), EXAONE_API_KEY (3번, LG K-EXAONE)
//   GEMINI_MODEL (선택, 기본 gemini-3.5-flash-lite), GROQ_MODEL (선택, 기본 openai/gpt-oss-120b)
//   EXAONE_MODEL (선택, 기본 k-exaone_v2.5), EXAONE_URL (선택, 기본 https://api.exaone.ai/v1/chat/completions)
// 자동 전환: 고른 LLM이 실패하면 키가 등록된 다른 LLM으로 넘겨 답한다(응답의 llm·fallback 필드로 표시).

const ALLOW = ["https://lloydknam.github.io"];
const PER_HOUR = 30;               // IP당 시간당 질문 수 (인스턴스 메모리 기준, 대략적 제한)
const hits = new Map();

const SYSTEM = "너는 한국 국가예산 자료를 설명하는 도우미다. 반드시 [자료]에 있는 내용만 근거로 답하고, 근거 문장 끝에 [번호]로 출처를 표시한다. " +
  "자료에 없는 내용은 '자료에서 확인되지 않음'이라고 말하고 추측하지 않는다. 금액은 자료의 단위를 그대로 쓴다. 한국어로 간결하게 답한다. " +
  "자료는 [사업]과 [재정통계] 두 종류다. 두 종류가 모두 있으면 답을 '■ 사업 자료'와 '■ 재정통계' 두 부분으로 나눠 쓰고, 한 종류만 있으면 그 부분만 쓴다.";

const SYSTEM_WEB = SYSTEM + " [외부자료]는 웹 검색 결과다. 외부자료에서 얻은 내용은 '■ 외부자료' 부분으로 나눠 쓰고, 출처를 [웹번호]로 표시한다. 예산 자료와 외부자료의 내용이 다르면 둘 다 밝힌다.";

export default {
  async fetch(req, env) {
    const origin = req.headers.get("Origin") || "";
    const cors = {
      "Access-Control-Allow-Origin": ALLOW.includes(origin) ? origin : ALLOW[0],
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    if (req.method !== "POST") return json({ error: "POST만 받습니다" }, 405, cors);
    if (!ALLOW.includes(origin)) return json({ error: "허용되지 않은 사이트입니다" }, 403, cors);

    const ip = req.headers.get("CF-Connecting-IP") || "unknown";
    const now = Date.now();
    const log = (hits.get(ip) || []).filter(t => now - t < 3600_000);
    if (log.length >= PER_HOUR) return json({ error: "질문이 많아 잠시 쉬어야 합니다. 1시간 뒤 다시 시도해 주세요." }, 429, cors);
    log.push(now); hits.set(ip, log);

    let body;
    try { body = await req.json(); } catch (e) { return json({ error: "요청 형식이 잘못됐습니다" }, 400, cors); }
    const q = String(body.q || "").slice(0, 300).trim();
    if (!q) return json({ error: "질문이 비어 있습니다" }, 400, cors);
    if (body.expand === true) {
      // 질문을 예산 사업 검색 키워드로 풀어 쓴다 (실패해도 사이트는 원래 질문으로 계속)
      try {
        const keywords = await expandKeywords(env, q);
        return json({ keywords }, 200, cors);
      } catch (e) {
        return json({ keywords: "", error: String(e.message || e).slice(0, 200) }, 200, cors);
      }
    }
    if (body.web_only === true && body.llm === "groq") {
      // Groq(gpt-oss-120b) 내장 browser_search 도구로 외부 검색
      try {
        const out = await groqSearch(env, q);
        return json({ web: [], text: out.text, model: out.model }, 200, cors);
      } catch (e) {
        const msg = String(e.message || e);
        const quota = e.status === 429 || /quota|rate limit/i.test(msg);
        const kst = new Date(Date.now() + 9 * 3600_000).toISOString().slice(0, 16).replace("T", " ");
        return json({ web: [], text: "", error: msg.slice(0, 200), quota, model: "openai/gpt-oss-120b", tool: "Groq 웹검색", checkedAt: kst + " KST" }, 200, cors);
      }
    }
    if (body.web_only === true) {
      // 검색 결과에 붙는 외부 검색결과 (LLM 선택과 무관, Gemini 검색 도구 사용)
      try {
        const { web } = await gemini(env, `다음 질문과 관련된 공개 자료(정부 발표, 공공기관 자료, 언론 보도)를 웹에서 찾아 주세요. 질문: ${q}`, true);
        return json({ web }, 200, cors);
      } catch (e) {
        // 할당량 초과(429 또는 quota 문구)일 때만 사이트에 한 줄로 알린다
        const msg = String(e.message || e);
        const quota = e.status === 429 || /quota|rate limit/i.test(msg);
        const kst = new Date(Date.now() + 9 * 3600_000).toISOString().slice(0, 16).replace("T", " ");
        return json({ web: [], error: msg.slice(0, 200), quota, model: env.GEMINI_MODEL || "gemini-3.5-flash-lite", tool: "Google 검색 도구", checkedAt: kst + " KST" }, 200, cors);
      }
    }
    const sources = (Array.isArray(body.sources) ? body.sources : []).slice(0, 10);
    const ctx = sources.map((s, i) =>
      `[${i + 1}] [${s.kind === "재정통계" ? "재정통계" : "사업"}] ${s.title} (${s.source})\n- 수치: ${String(s.facts || "").slice(0, 1500)}${s.text ? `\n- 사업설명: ${String(s.text).slice(0, 1500)}` : ""}`
    ).join("\n\n");
    const user = `[자료]\n${ctx || "(관련 자료 없음)"}\n\n[질문] ${q}`;
    const llm = body.llm || "gemini";
    const webOn = body.web === true && llm === "gemini";

    // 자동 전환(failover): 고른 LLM이 실패(시간초과·할당량·오류·빈 답변)하면 다음 LLM으로 넘긴다.
    // 순서: 고른 LLM → 나머지(Gemini→Groq→EXAONE 순), 키가 없는 LLM은 건너뛴다.
    // 전체 시간 예산(TOTAL_MS)을 넘지 않게 각 시도의 시간초과를 줄여 Cloudflare 524(100초)를 피한다.
    const order = [llm, ...ORDER.filter(k => k !== llm)].filter(k => ORDER.includes(k) && env[KEYS[k]]);
    const deadline = Date.now() + TOTAL_MS;
    const tried = [];
    for (const k of order) {
      const left = deadline - Date.now();
      if (left < MIN_TRY_MS) break;
      const ms = Math.min(LIMIT_MS[k], left);
      try {
        const out = k === "groq" ? await groq(env, user, ms) : k === "exaone" ? await exaone(env, user, ms) : await gemini(env, user, webOn && k === llm, ms);
        if (!String(out.text || "").trim()) throw new Error("빈 답변");
        return json({ answer: out.text, model: out.model, llm: k, name: NAMES[k], web: out.web || [], fallback: tried }, 200, cors);
      } catch (e) {
        const msg = e.name === "TimeoutError" || e.name === "AbortError" ? `시간초과(${Math.round(ms / 1000)}초)` : String(e.message || e);
        tried.push({ llm: k, name: NAMES[k], error: msg.slice(0, 120) });
      }
    }
    const why = tried.map(t => `${t.name}: ${t.error}`).join(" / ") || "사용 가능한 LLM 키가 없습니다";
    return json({ error: `모든 LLM이 실패했습니다 (${why})`.slice(0, 400), fallback: tried }, 502, cors);
  },
};

const ORDER = ["gemini", "groq", "exaone"];
const KEYS = { gemini: "GEMINI_API_KEY", groq: "GROQ_API_KEY", exaone: "EXAONE_API_KEY" };
const NAMES = { gemini: "Gemini", groq: "Groq", exaone: "EXAONE" };
const LIMIT_MS = { gemini: 30000, groq: 30000, exaone: 45000 }; // LLM별 1회 시도 시간초과
const TOTAL_MS = 85000;   // 전체 예산 (Cloudflare 100초 제한보다 여유 있게)
const MIN_TRY_MS = 8000;  // 남은 시간이 이보다 짧으면 다음 LLM을 시도하지 않는다

async function gemini(env, user, webOn = false, ms = 30000) {
  const model = env.GEMINI_MODEL || "gemini-3.5-flash-lite";
  const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
    method: "POST",
    signal: AbortSignal.timeout(ms),
    headers: { "Content-Type": "application/json", "x-goog-api-key": env.GEMINI_API_KEY },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: webOn ? SYSTEM_WEB : SYSTEM }] },
      contents: [{ role: "user", parts: [{ text: user }] }],
      generationConfig: { temperature: 0.2, maxOutputTokens: 900 },
      ...(webOn ? { tools: [{ google_search: {} }] } : {}),
    }),
  });
  const j = await r.json();
  if (!r.ok) { const err = new Error(j.error?.message || "Gemini 호출 실패"); err.status = r.status; throw err; }
  const cand = j.candidates?.[0] || {};
  const web = (cand.groundingMetadata?.groundingChunks || []).map(c => c.web).filter(Boolean)
    .map(w => ({ title: w.title || w.domain || "출처", url: w.uri, domain: w.domain || "" })).filter(w => w.url).slice(0, 6);
  return { text: (cand.content?.parts || []).map(p => p.text || "").join(""), model: j.modelVersion || model, web };
}

async function expandKeywords(env, q) {
  const r = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    signal: AbortSignal.timeout(8000),
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${env.GROQ_API_KEY}` },
    body: JSON.stringify({
      model: "openai/gpt-oss-120b",
      temperature: 0.1,
      max_completion_tokens: 200,
      reasoning_effort: "low",
      messages: [
        { role: "system", content: "너는 한국 국가예산 세부사업을 찾기 위한 검색어 도우미다. 사용자의 질문을 예산 사업명에 쓰일 법한 한국어 키워드로 바꿔라. 줄임말·외래어·신조어는 풀어 쓴다(예: 케어테크 → 노인 돌봄 요양 복지 기술). 키워드 5~8개를 쉼표로 구분해 한 줄로만 출력한다. 설명은 쓰지 않는다." },
        { role: "user", content: q },
      ],
    }),
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error?.message || "키워드 확장 실패");
  return String(j.choices?.[0]?.message?.content || "").replace(/[\r\n]+/g, " ").replace(/[^가-힣A-Za-z0-9,\s]/g, " ").replace(/\s+/g, " ").trim().slice(0, 120);
}

async function groqSearch(env, q) {
  const model = "openai/gpt-oss-120b";
  const r = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    signal: AbortSignal.timeout(45000),
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${env.GROQ_API_KEY}` },
    body: JSON.stringify({
      model,
      temperature: 0.2,
      max_completion_tokens: 1200,
      reasoning_effort: "low",
      tool_choice: "required",
      tools: [{ type: "browser_search" }],
      messages: [
        { role: "system", content: "너는 공개 자료를 웹에서 찾아 요약하는 도우미다. 지금은 2026년 11월이다. 가장 최신 자료(2026년 발표)를 우선하고, 연도가 오래된 자료는 그렇다고 밝힌다. 정부 발표, 공공기관 자료, 언론 보도를 찾아 한국어로 간결히 요약하고, 근거가 된 출처의 제목과 URL을 함께 적는다. 인용 표식(【…】)은 쓰지 않는다." },
        { role: "user", content: `다음 질문과 관련된 공개 자료를 찾아 주세요. 질문: ${q}` },
      ],
    }),
  });
  const j = await r.json();
  if (!r.ok) { const err = new Error(j.error?.message || "Groq 검색 호출 실패"); err.status = r.status; throw err; }
  const text = String(j.choices?.[0]?.message?.content || "").replace(/【[^】]*】/g, "").replace(/[ \t]+\n/g, "\n").trim();
  return { text, model: j.model || model };
}

async function groq(env, user, ms = 30000) {
  const r = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    signal: AbortSignal.timeout(ms),
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${env.GROQ_API_KEY}` },
    body: JSON.stringify({
      model: env.GROQ_MODEL || "openai/gpt-oss-120b",
      temperature: 0.2,
      max_tokens: 900,
      messages: [{ role: "system", content: SYSTEM }, { role: "user", content: user }],
    }),
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error?.message || "Groq 호출 실패");
  return { text: j.choices?.[0]?.message?.content || "", model: j.model || env.GROQ_MODEL || "openai/gpt-oss-120b" };
}

async function exaone(env, user, ms = 45000) {
  const r = await fetch(env.EXAONE_URL || "https://api.exaone.ai/v1/chat/completions", {
    method: "POST",
    signal: AbortSignal.timeout(ms),
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${env.EXAONE_API_KEY}` },
    body: JSON.stringify({
      model: env.EXAONE_MODEL || "k-exaone_v2.5",
      reasoning_effort: "low",
      temperature: 0.2,
      max_tokens: 900,
      messages: [{ role: "system", content: SYSTEM }, { role: "user", content: user }],
    }),
  });
  const raw = await r.text();
  let j; try { j = JSON.parse(raw); } catch (e) { throw new Error(`EXAONE 응답 오류(${r.status})`); }
  if (!r.ok) throw new Error(j.error?.message || j.message || `EXAONE 호출 실패(${r.status})`);
  return { text: (j.choices?.[0]?.message?.content || "").replace(/<think>[\s\S]*?<\/think>/g, "").trim(), model: j.model || env.EXAONE_MODEL || "k-exaone_v2.5" };
}

function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), { status, headers: { ...headers, "Content-Type": "application/json; charset=utf-8" } });
}
