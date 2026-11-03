"""열린재정 Open API 수집 뼈대 (사용자 PC에서 실행).

주의: 이 샌드박스에서는 openfiscaldata.go.kr 에 접속이 차단되어
엔드포인트명과 응답 필드명을 실제로 검증하지 못했습니다.
아래 ENDPOINTS 와 FIELD_MAP 은 열린재정 Open API 명세서(인증키 발급 후 확인 가능)에
맞춰 직접 고쳐야 합니다. 명세와 다르면 KeyError 나 빈 결과가 나옵니다.

사용법:
  export OPENFISCAL_KEY=발급받은키
  python scripts/fetch_openfiscal.py --year 2027
  python scripts/build.py
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://openapi.openfiscaldata.go.kr"  # 명세서로 확인 후 수정
# 명세서에서 확인해 채우세요 (예시 이름은 추정치입니다)
ENDPOINTS = {
    "budget": "TODO_BUDGET_ENDPOINT",        # 세부사업별 정부안·국회확정액
    "exec": "TODO_EXECUTION_ENDPOINT",       # 단위사업별 지출·이월·불용
}
# 응답 필드 -> 내부 필드 매핑 (명세서 기준으로 수정)
FIELD_MAP = {
    "project_name": "TODO_사업명_필드",
    "field": "TODO_분야_필드",
    "gov_amount": "TODO_정부안_필드",
    "na_amount": "TODO_국회확정_필드",
    "spent": "TODO_지출_필드",
    "unused": "TODO_불용_필드",
}
OUT = Path(__file__).resolve().parent.parent / "data" / "budget.json"


def call(endpoint: str, key: str, **params) -> list[dict]:
    if endpoint.startswith("TODO"):
        sys.exit(f"엔드포인트가 아직 설정되지 않았습니다: {endpoint}. ENDPOINTS를 먼저 채우세요.")
    q = urllib.parse.urlencode({"KEY": key, "Type": "json", "pIndex": 1, "pSize": 1000, **params})
    url = f"{BASE}/{endpoint}?{q}"
    with urllib.request.urlopen(url, timeout=30) as r:
        body = json.loads(r.read().decode("utf-8"))
    # 응답 구조는 명세서 확인 필요: 대개 {"<서비스명>": [{"head": ...}, {"row": [...]}]}
    rows = []
    for block in body.values():
        for part in block if isinstance(block, list) else []:
            rows.extend(part.get("row", []))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2027)
    args = ap.parse_args()
    key = os.environ.get("OPENFISCAL_KEY")
    if not key:
        sys.exit("OPENFISCAL_KEY 환경변수가 없습니다.")
    budget_rows = call(ENDPOINTS["budget"], key, year=args.year)
    exec_rows = call(ENDPOINTS["exec"], key, year=args.year - 2)
    # TODO: budget_rows / exec_rows 를 build 가 읽는 projects 구조로 변환
    # 구조: {"id","name","field","ministry","years":{y:{"gov","na"}},"exec":{y:{"budget","spent","unused","rate"}},"docs":[]}
    print(f"수집: 예산 {len(budget_rows)}행, 집행 {len(exec_rows)}행 (변환 로직은 TODO)")
    OUT.parent.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    main()
