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
import re
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

# 확인된 실제 row 키 (2027 응답으로 검증)
FIELD = {
    "ministry": "OFFC_NM",   # 소관
    "fund": "FSCL_NM",       # 회계
    "field": "FLD_NM",       # 분야
    "sector": "SECT_NM",     # 부문
    "program": "PGM_NM",     # 프로그램
    "activity": "ACTV_NM",   # 단위사업
    "project": "SACTV_NM",   # 세부사업
    "amount": "Y_YY_MEDI_KCUR_AMT",          # 금액 (정부안으로 추정)
    "amount_alt": "Y_YY_DFN_MEDI_KCUR_AMT",  # 금액 (국회 확정으로 추정, 2026으로 검증 중)
}
UNIT_DIVISOR = 100000  # 천원 -> 억원 (천원 단위 추정, 결과 합계로 검증)


def call(code: str, key: str, **params) -> list[dict]:
    rows, index = [], 1
    while True:
        q = urllib.parse.urlencode({"KEY": key, "Type": "json", "pIndex": index,
                                    "pSize": PAGE_SIZE, **params})
        try:
            with urllib.request.urlopen(f"{BASE}/{code}?{q}", timeout=60) as r:
                status = r.status
                raw = r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:   # 키는 주소에 있으므로 주소는 출력하지 않음
            sys.exit(f"[{code}] HTTP {e.code} 오류. 응답 앞부분: {e.read()[:300]!r}")
        except urllib.error.URLError as e:
            sys.exit(f"[{code}] 연결 실패: {e.reason}")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            text = re.sub(r"<style.*?</style>|<script.*?</script>", " ", raw, flags=re.S)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            sys.exit(f"[{code}] JSON이 아닌 응답 (HTTP {status}). 페이지 문구: {text[:500]}")
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

    summary = {}
    all_projects = {}
    for year in (args.year - 1, args.year):
        rows = call(BUDGET_CODE, key, FSCL_YY=year)
        if year == args.year:
            inspect(rows, f"{BUDGET_CODE} {year}")
            if args.inspect:
                return
        print(f"\n[{year}] 행 수 {len(rows)}")
        gov_sum = sum(to_num(r.get(FIELD["amount"])) or 0 for r in rows)
        alt_sum = sum(to_num(r.get(FIELD["amount_alt"])) or 0 for r in rows)
        print(f"  {FIELD['amount']} 합계: {gov_sum:,} (천원 가정 시 약 {gov_sum/UNIT_DIVISOR:,.0f}억원)")
        print(f"  {FIELD['amount_alt']} 합계: {alt_sum:,} (0이 아니면 확정액 후보)")
        for r in rows:
            k = (r.get(FIELD["ministry"]), r.get(FIELD["fund"]), r.get(FIELD["field"]),
                 r.get(FIELD["sector"]), r.get(FIELD["program"]), r.get(FIELD["activity"]),
                 r.get(FIELD["project"]))
            pj = all_projects.setdefault(k, {
                "id": "", "name": r.get(FIELD["project"]) or "", "field": r.get(FIELD["field"]) or "",
                "ministry": r.get(FIELD["ministry"]) or "", "years": {}, "exec": {}, "docs": []})
            y = pj["years"].setdefault(str(year), {"gov": 0, "na": 0})
            y["gov"] += (to_num(r.get(FIELD["amount"])) or 0)
            y["na"] += (to_num(r.get(FIELD["amount_alt"])) or 0)

    projects = []
    for i, pj in enumerate(all_projects.values()):
        pj["id"] = f"B{i+1:05d}"
        for y in pj["years"].values():
            y["gov"] = round(y["gov"] / UNIT_DIVISOR)
            y["na"] = round(y["na"] / UNIT_DIVISOR)
        projects.append(pj)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"notice": "", "unit": "억원 (천원 가정)", "projects": projects, "quality": []},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n저장: {OUT} ({len(projects)}개 세부사업, 연도 {args.year-1}·{args.year}). 집행·검토문서는 아직 없음.")


def to_num(v):
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
