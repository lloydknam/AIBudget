# AI분석 중계 서버 (Cloudflare Workers)

정적 사이트(GitHub Pages)는 API 키를 숨길 수 없어서, 키는 이 Worker의 환경변수에만 둡니다.

## 배포 순서
1. Google AI Studio에서 Gemini API 키 발급 (기본 LLM 1번).
2. (선택) Groq 콘솔에서 API 키 발급 (LLM 2번).
3. Cloudflare 계정에서 Workers 새로 만들기 → `worker/ai-proxy.js` 내용 붙여넣기 → 배포.
4. Worker 설정 > Variables and Secrets에 `GEMINI_API_KEY`, `GROQ_API_KEY`를 **Secret**으로 추가.
5. 배포 주소 `https://<이름>.<계정>.workers.dev/ask` 를 `index.html`의 `AI_API` 상수에 넣고 커밋.

## 참고
- 허용 사이트는 `ALLOW` 목록(lloydknam.github.io)만. 다른 사이트에서 호출하면 403.
- 호출 제한은 Worker 인스턴스 메모리 기준이라 대략적입니다. 정확한 제한이 필요하면 Cloudflare Rate Limiting 규칙을 추가하세요.
- 모델 이름(`GEMINI_MODEL`, `GROQ_MODEL`)은 무료 티어 지원 여부를 확인한 뒤 바꿀 수 있습니다.

## 현재 배포
- Worker: `aibudget-ai` (https://aibudget-ai.lloydnam.workers.dev/ask)
- 환경변수: `GEMINI_API_KEY`(Secret), `GEMINI_MODEL=gemini-3.5-flash-lite`
- `gemini-3.8-flash`는 이 Worker에서 응답이 100초 넘게 걸려 시간초과(524)가 나서 Flash-Lite로 바꿨습니다.
- 배치(Placement): Region → GCP `asia-northeast3`(서울). 기본 배치에서는 요청이 Gemini 미지원 지역 경유로 처리돼 "User location is not supported" 오류가 났습니다.
- 3번 LLM: LG K-EXAONE 2.5 (`EXAONE_API_KEY`, 모델 `k-exaone_v2.5`, `reasoning_effort: low`). 키는 30일마다 만료되고 하루 호출 한도가 있으며 비상업적 사용만 허용됩니다.
- 2번 LLM: Groq `openai/gpt-oss-120b` (환경변수 `GROQ_MODEL`). `llama-3.3-70b-versatile`은 이 계정에서 "does not exist or you do not have access" 오류가 나서 바꿨습니다.
