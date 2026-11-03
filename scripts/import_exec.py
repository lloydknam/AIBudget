"""브라우저에서 받은 aibudget_exec.json (열린재정 ExpendituresSettlement, 백만원) 을 data/budget.json 에 붙입니다.

- 결산은 단위사업(ACTV) 단위입니다. (소관, 정규화 단위사업명) 으로 묶고 회계·기금별 금액은 합산합니다.
- 각 세부사업은 자기 단위사업(최근 연도 기준)과 연결합니다. 소관이 바뀐 사업은 이전 소관명으로도 찾습니다.
- 제외: 기금 '예치금및유가증권매입' 지출목, '여유자금운용' 단위사업 (자금 운용이라 집행률 의미 없음)

사용법: python scripts/import_exec.py <aibudget_exec.json 경로>
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUDGET = ROOT / "data" / "budget.json"


def norm(s: str) -> str:
    return re.sub(r"[\sㆍ·・‧∙]", "", s or "")


def main(src: str):
    raw = json.loads(Path(src).read_text(encoding="utf-8"))
    data = json.loads(BUDGET.read_text(encoding="utf-8"))
    years = raw["years"]
    dm, df = raw["dicts"]["ministry"], raw["dicts"]["fund"]

    units = {}
    for r in raw["rows"]:
        ministry, fund, activity, program = dm[r[0]], df[r[1]], r[2], r[3]
        key = (ministry, norm(activity))
        u = units.setdefault(key, {"ministry": ministry, "activity": activity, "program": program,
                                   "funds": set(), "years": defaultdict(lambda: [0, 0, 0, 0])})
        u["funds"].add(fund)
        for y, v in zip(years, r[4:]):
            if not v:
                continue
            e = u["years"][y]
            for i in range(4):
                e[i] += v[i]

    to_eok = lambda v: round(v / 100, 1)  # 백만원 -> 억원
    unit_list, index = [], {}
    for key, u in units.items():
        ys = {}
        for y, (cur, spent, carry, unused) in sorted(u["years"].items()):
            if cur <= 0 and spent <= 0:
                continue
            ys[str(y)] = {"cur": to_eok(cur), "spent": to_eok(spent), "carry": to_eok(carry),
                          "unused": to_eok(unused), "rate": round(spent / cur * 100, 1) if cur > 0 else None}
        if not ys:
            continue
        index[key] = len(unit_list)
        unit_list.append({"ministry": u["ministry"], "activity": u["activity"], "program": u["program"],
                          "funds": sorted(u["funds"]), "years": ys})

    linked = 0
    for p in data["projects"]:
        p.pop("unit", None)
        for m in [p["ministry"], *reversed(p.get("prev_ministry", []))]:
            k = (m, norm(p.get("activity")))
            if k in index:
                p["unit"] = index[k]
                linked += 1
                break

    data["units"] = unit_list
    data["exec_source"] = raw["source"]
    data["exec_years"] = years
    BUDGET.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with_exec = [p for p in data["projects"] if "unit" in p]
    old = [p for p in data["projects"] if any(y in p["years"] for y in ("2024", "2025"))]
    old_linked = [p for p in old if "unit" in p]
    print(f"단위사업 {len(unit_list)}개, 결산과 연결된 세부사업 {linked}/{len(data['projects'])}개")
    print(f"  2024·2025 예산이 있는 세부사업 중 연결: {len(old_linked)}/{len(old)}개")
    for y in years:
        cur = sum(u["years"].get(str(y), {}).get("cur", 0) for u in unit_list)
        sp = sum(u["years"].get(str(y), {}).get("spent", 0) for u in unit_list)
        un = sum(u["years"].get(str(y), {}).get("unused", 0) for u in unit_list)
        ca = sum(u["years"].get(str(y), {}).get("carry", 0) for u in unit_list)
        print(f"  {y}: 현액 {cur/10000:,.1f}조, 지출 {sp/10000:,.1f}조, 이월 {ca/10000:,.1f}조, 불용 {un/10000:,.1f}조")


if __name__ == "__main__":
    main(sys.argv[1])
