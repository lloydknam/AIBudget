// 클사무관의 예산 프리즘 · AI분석 중계 서버 (Cloudflare Workers 무료 플랜)
// 역할: 브라우저에 API 키를 노출하지 않고, 허용된 사이트에서 온 질문만 LLM에 전달한다.
// 환경변수(Worker 설정 > Variables and Secrets):
//   GEMINI_API_KEY (필수, 기본 LLM 1번), GROQ_API_KEY (2번), EXAONE_API_KEY (3번, LG K-EXAONE)
//   GEMINI_MODEL (선택, 기본 gemini-3.5-flash-lite), GROQ_MODEL (선택, 기본 llama-3.3-70b-versatile)
//   EXAONE_MODEL (선택, 기본 k-exaone_v2.5), EXAONE_URL (선택, 기본 https://api.exaone.ai/v1/chat/completions)

const ALLOW = ["https://lloydknam.github.io"];
const PER_HOUR = 30;               // IP당 시간당 질문 수 (인스턴스 메모리 기준, 대략적 제한)
const hits = new Map();

const SYSTEM = "너는 한국 국가예산 자료를 설명하는 도우미다. 반드시 [자료]에 있는 내용만 근거로 답하고, 근거 문장 끝에 [번호]로 출처를 표시한다. " +
  "자료에 없는 내용은 '자료에서 확인되지 않음'이라고 말하고 추측하지 않는다. 금액은 자료의 단위(억원)를 그대로 쓴다. 한국어로 간결하게 답한다.";

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
    const sources = (Array.isArray(body.sources) ? body.sources : []).slice(0, 6);
    const ctx = sources.map((s, i) =>
      `[${i + 1}] ${s.title} (${s.source})\n- 수치: ${String(s.facts || "").slice(0, 800)}\n- 사업설명: ${String(s.text || "").slice(0, 1500)}`
    ).join("\n\n");
    const user = `[자료]\n${ctx || "(관련 자료 없음)"}\n\n[질문] ${q}`;

    try {
      const answer = body.llm === "groq" ? await groq(env, user) : body.llm === "exaone" ? await exaone(env, user) : await gemini(env, user);
      return json({ answer }, 200, cors);
    } catch (e) {
      return json({ error: String(e.message || e).slice(0, 200) }, 502, cors);
    }
  },
};

async function gemini(env, user) {
  const model = env.GEMINI_MODEL || "gemini-3.5-flash-lite";
  const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
    method: "POST",
    signal: AbortSignal.timeout(30000),
    headers: { "Content-Type": "application/json", "x-goog-api-key": env.GEMINI_API_KEY },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: SYSTEM }] },
      contents: [{ role: "user", parts: [{ text: user }] }],
      generationConfig: { temperature: 0.2, maxOutputTokens: 900 },
    }),
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error?.message || "Gemini 호출 실패");
  return (j.candidates?.[0]?.content?.parts || []).map(p => p.text || "").join("");
}

async function groq(env, user) {
  const r = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    signal: AbortSignal.timeout(30000),
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${env.GROQ_API_KEY}` },
    body: JSON.stringify({
      model: env.GROQ_MODEL || "llama-3.3-70b-versatile",
      temperature: 0.2,
      max_tokens: 900,
      messages: [{ role: "system", content: SYSTEM }, { role: "user", content: user }],
    }),
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error?.message || "Groq 호출 실패");
  return j.choices?.[0]?.message?.content || "";
}

async function exaone(env, user) {
  const r = await fetch(env.EXAONE_URL || "https://api.exaone.ai/v1/chat/completions", {
    method: "POST",
    signal: AbortSignal.timeout(45000),
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
  return (j.choices?.[0]?.message?.content || "").replace(/<think>[\s\S]*?<\/think>/g, "").trim();
}

function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), { status, headers: { ...headers, "Content-Type": "application/json; charset=utf-8" } });
}
