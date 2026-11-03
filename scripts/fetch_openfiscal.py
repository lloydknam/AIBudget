"""열린재정 Open API 수집 (사용자 PC에서 실행).

확인된 부분 (공개 레퍼런스 코드 src/api/client.ts, src/api/catalog.ts 기준):
  - 베이스 URL: https://openapi.openfiscaldata.go.kr
  - 호출: /{코드}?KEY=...&Type=json&pIndex=1&pSize=1000&FSCL_YY=연도
  - 응답: {코드: [{head: [{list_total_count}, {RESULT: {CODE, MESSAGE}}]}, {row: [...]}]}
          본문이 JSON 문자열로 한 번 더 감싸져 있어 두 번 파싱합니다.
  - 예산: ExpenditureBudgetInit5 (세부사업 예산편성현황, 필수 FSCL_YY)
  - 집행: FSCPGMEXEC (사업 집행실적, YEAR, PGM_CD 필요)

아직 확인하지 못한 부분 (이 환경에서 API에 접속할 수 없어서):
  - 금액 필드명(정부안, 국회확정, 지출, 불용)과 row 키 이름
  - 그래서 첫 실행 시 row 키 목록을 출력합니다. 출력된 이름을 AMOUNT_FIELDS 에 채우세요.
  - 집행 데이터 키(FSCPGMEXEC)의 필드명과 PGM_CD 연결 방식도 같은 방식으로 확인합니다.

사용법:
  export OPENFISCAL_KEY=발급받은키
  python scripts/fetch_openfiscal.py --year 2027 --inspect    # 키 목록만 출력
  python scripts/fetch_openfiscal.py --year 2027              # data/budget.json 생성
  python scripts/build.py
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://openapi.openfiscaldata.go.kr"
BUDGET_CODE = "ExpenditureBudgetInit5"
EXEC_CODE = "FSCPGMEXEC"
PAGE_SIZE = 1000
OUT = Path(__file__).resolve().parent.parent / "data" / "budget.json"

# 내부 필드 -> 실제 row 키. 첫 실행(--inspect) 결과를 보고 채우세요. 비어 있으면 실행이 멈춥니다.
AMOUNT_FIELDS = {
    "gov_amount": "",     # 정부안 금액 필드
    "na_amount": "",      # 국회 확정 금액 필드
    "project_name": "",   # 세부사업명 필드 (예: SACTV_NM 추정, 확인 필요)
    "field_name": "",     # 분야명 필드 (예: FLD_NM 추정, 확인 필요)
    "ministry_name": "",  # 소관명 필드 (예: OFFC_NM 추정, 확인 필요)
    "program_code": "",   # 집행 조회용 사업 코드 필드
    "spent": "",          # 집행(지출) 필드
    "unused": "",         # 불용 필드
}


def call(code: str, key: str, **params) -> list[dict]:
    rows, index = [], 1
    while True:
        q = urllib.parse.urlencode({"KEY": key, "Type": "json", "pIndex": index,
                                    "pSize": PAGE_SIZE, **params})
        with urllib.request.urlopen(f"{BASE}/{code}?{q}", timeout=60) as r:
            raw = r.read().decode("utf-8")
        body = json.loads(raw)
        if isinstance(body, str):          # 레퍼런스처럼 이중 인코딩된 경우
            body = json.loads(body)
        if code not in body:               # 오류 응답
            flat = body.get("RESULT", {})
            sys.exit(f"[{code}] 오류: {flat.get('CODE')} {flat.get('MESSAGE')}")
        head, block = body[code][0]["head"], body[code][1]
        result = head[1]["RESULT"]
        if result["CODE"] == "INFO-200":   # 데이터 없음
            break
        if result["CODE"] != "INFO-000":
            sys.exit(f"[{code}] 오류: {result['CODE']} {result['MESSAGE']}")
        page = block.get("row", [])
        rows.extend(page)
        total = head[0]["list_total_count"]
        if len(rows) >= total or not page:
            break
        index += 1
    return rows


def inspect(rows: list[dict], label: str):
    print(f"\n[{label}] 행 수: {len(rows)}")
    if rows:
        print("키 목록:", sorted(rows[0].keys()))
        print("첫 행 샘플:", json.dumps(rows[0], ensure_ascii=False)[:800])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2027)
    ap.add_argument("--inspect", action="store_true", help="응답 키만 출력하고 종료")
    args = ap.parse_args()
    key = os.environ.get("OPENFISCAL_KEY")
    if not key:
        sys.exit("OPENFISCAL_KEY 환경변수가 없습니다.")

    budget_rows = call(BUDGET_CODE, key, FSCL_YY=args.year)
    inspect(budget_rows, f"{BUDGET_CODE} {args.year}")
    if args.inspect:
        return

    missing = [k for k, v in AMOUNT_FIELDS.items() if not v]
    if missing:
        sys.exit(f"AMOUNT_FIELDS가 비어 있습니다: {missing}. --inspect 결과로 채운 뒤 다시 실행하세요.")

    # 변환: 세부사업 단위로 묶고, 연도별 정부안만 우선 채움 (국회 확정·집행은 후속 작업)
    m = AMOUNT_FIELDS
    projects = []
    for i, r in enumerate(budget_rows):
        projects.append({
            "id": f"B{i+1:05d}",
            "name": str(r.get(m["project_name"], "")),
            "field": str(r.get(m["field_name"], "")),
            "ministry": str(r.get(m["ministry_name"], "")),
            "years": {str(args.year): {"gov": to_num(r.get(m["gov_amount"])), "na": None}},
            "exec": {},
            "docs": [],
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"notice": "", "unit": "억원", "projects": projects, "quality": []},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장: {OUT} ({len(projects)}건). 집행·검토문서·국회 확정은 아직 채워지지 않았습니다.")


def to_num(v):
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
