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
