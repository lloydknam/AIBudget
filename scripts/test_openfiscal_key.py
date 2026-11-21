"""열린재정 OPEN API 인증키 확인 (GitHub Actions에서만 실행)
키 이름: OPENFISCAL_KEY 가 있으면 그것을, 없으면 DATA_GO_KR_KEY 를 쓴다.
응답 앞부분만 출력한다. 키 값은 출력하지 않는다."""
import os, urllib.request, urllib.parse, json

KEY = os.environ.get("OPENFISCAL_KEY") or os.environ.get("DATA_GO_KR_KEY") or ""
print("키 길이:", len(KEY))  # 값은 출력하지 않음
if not KEY:
    raise SystemExit("키가 비어 있습니다. OPENFISCAL_KEY 또는 DATA_GO_KR_KEY 시크릿을 확인하세요.")

# 열린재정 OPEN API 호출 형식 (서비스명은 예시 — 응답의 결과코드로 키 유효성을 본다)
for svc in ["BudgetDetail", "ExpBudgetDetail", "ExpBudgetSum"]:
    q = urllib.parse.urlencode({"KEY": KEY, "Type": "json", "pIndex": 1, "pSize": 2})
    url = f"https://openapi.openfiscaldata.go.kr/{svc}?{q}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
    except Exception as e:
        body = f"요청 실패: {type(e).__name__} {e}"
    print(f"--- {svc} ---")
    import re
    text = re.sub(r"<style.*?</style>|<script.*?</script>|<[^>]+>", " ", body, flags=re.S)
    text = re.sub(r"\s+", " ", text).strip()
    print("본문 텍스트:", text[:400])
    print("응답 길이:", len(body), "| 첫 바이트:", body[:60].replace("\n"," "))
