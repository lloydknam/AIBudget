"""브라우저에서 받은 aibudget_data.json (열린재정 TotalExpenditure5, 백만원) -> data/budget.json (억원).

사용법: python scripts/import_browser.py <aibudget_data.json 경로>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "budget.json"


def main(src: str):
    raw = json.loads(Path(src).read_text(encoding="utf-8"))
    cols = raw["columns"]
    d = raw["dicts"]
    years = raw["years"]
    to_eok = lambda v: None if v is None else round(v / 100, 1)  # 백만원 -> 억원

    projects = []
    for i, r in enumerate(raw["rows"]):
        row = dict(zip(cols, r))
        y = {}
        for yr in years:
            g, n = row[f"gov{yr}"], row[f"na{yr}"]
            if g is None and n is None:
                continue
            y[str(yr)] = {"gov": to_eok(g), "na": to_eok(n) if n else None}
        projects.append({
            "id": f"B{i+1:05d}",
            "name": row["project"],
            "ministry": d["ministry"][row["ministry"]],
            "fund": d["fund"][row["fund"]],
            "field": d["field"][row["field"]],
            "sector": d["sector"][row["sector"]],
            "program": d["program"][row["program"]],
            "activity": d["activity"][row["activity"]],
            "years": y,
            "exec": {},
            "docs": [],
        })

    totals = {}
    for yr in years:
        g = sum((p["years"].get(str(yr), {}).get("gov") or 0) for p in projects)
        n = sum((p["years"].get(str(yr), {}).get("na") or 0) for p in projects)
        totals[str(yr)] = {"gov": round(g), "na": round(n)}

    out = {
        "notice": "",
        "source": raw["source"],
        "fetched_at": raw["fetched_at"],
        "unit": "억원",
        "basis": "총지출",
        "totals": totals,
        "projects": projects,
        "quality": [],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"저장 {OUT}: 세부사업 {len(projects)}개")
    for yr, t in totals.items():
        print(f"  {yr}: 정부안 {t['gov']/10000:,.1f}조, 국회확정 {t['na']/10000:,.1f}조")


if __name__ == "__main__":
    main(sys.argv[1])
