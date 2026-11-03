"""브라우저에서 받은 aibudget_data.json (열린재정 TotalExpenditure5, 백만원) -> data/budget.json (억원).

연도 간 같은 사업 연결 규칙:
  1) 사업명 정규화: 띄어쓰기·가운뎃점 차이 무시
  2) 기획예산처 아래 '사업명(원부처)' 형태로 일괄 계상된 사업은 괄호 속 부처 표기를 떼고 비교
  3) 이름이 같고 연도가 겹치지 않는 묶음은 소관이 바뀐 같은 사업으로 보고 합침
     (예: 2026 기획재정부 '국고채이자상환' -> 2027 재정경제부 '국고채이자상환')
같은 연도에 같은 이름이 여러 회계·프로그램에 있으면 합산합니다.

사용법: python scripts/import_browser.py <aibudget_data.json 경로>
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "budget.json"
POOLED = "기획예산처"
SUFFIX = re.compile(r"\(([가-힣]{1,10}(?:부|처|청|위|원|실))\)$")


def norm(s: str) -> str:
    s = re.sub(r"[\sㆍ·・‧∙]", "", s or "")
    return s.replace("（", "(").replace("）", ")")


def main(src: str):
    raw = json.loads(Path(src).read_text(encoding="utf-8"))
    cols, d, years = raw["columns"], raw["dicts"], raw["years"]

    # 1) (소관, 정규화 사업명) 단위로 연도별 합산
    groups = {}
    for r in raw["rows"]:
        row = dict(zip(cols, r))
        ministry = d["ministry"][row["ministry"]]
        name = row["project"] or ""
        pooled_from = None
        if ministry == POOLED:
            m = SUFFIX.search(name.strip())
            if m:
                pooled_from = m.group(1)
                name = name.strip()[: m.start()]
        key = (ministry, norm(name))
        g = groups.setdefault(key, {"names": {}, "meta": {}, "years": defaultdict(lambda: [0, 0, False]),
                                    "pooled_from": pooled_from})
        for y in years:
            gv, nv = row[f"gov{y}"], row[f"na{y}"]
            if not gv and not nv:   # 없거나 0원인 빈 행은 해당 연도 없음으로 처리
                continue
            e = g["years"][y]
            e[0] += gv or 0
            e[1] += nv or 0
            e[2] = e[2] or bool(nv)
            g["names"][y] = name.strip()
            g["meta"][y] = {k: d[k][row[k]] for k in ("fund", "field", "sector", "program", "activity")}

    # 2) 이름이 같고 연도가 겹치지 않는 묶음 합치기 (소관 변경)
    by_name = defaultdict(list)
    for key, g in groups.items():
        if g["years"]:          # 모든 연도가 0원인 묶음은 제외
            by_name[key[1]].append((key, g))
    merged = []
    for name_key, items in by_name.items():
        items.sort(key=lambda kg: min(kg[1]["years"]))
        chains = []
        for key, g in items:
            ys = set(g["years"])
            for ch in chains:
                if not (ys & ch["ys"]) and min(ys) > max(ch["ys"]):
                    ch["parts"].append((key, g)); ch["ys"] |= ys
                    break
            else:
                chains.append({"parts": [(key, g)], "ys": set(ys)})
        merged.extend(chains)

    to_eok = lambda v: round(v / 100, 1)  # 백만원 -> 억원
    projects = []
    for ch in merged:
        yrs, names, meta, ministries = {}, {}, {}, []
        pooled_from = None
        for key, g in ch["parts"]:
            ministries.append(key[0])
            pooled_from = g["pooled_from"] or pooled_from
            for y, (gv, nv, has_na) in g["years"].items():
                yrs[str(y)] = {"gov": to_eok(gv), "na": to_eok(nv) if has_na else None}
            names.update(g["names"]); meta.update(g["meta"])
        last = max(names)
        ministry = ministries[-1]
        p = {"name": names[last], "ministry": ministry, **meta[last], "years": dict(sorted(yrs.items())),
             "exec": {}, "docs": []}
        prev = [m for m in dict.fromkeys(ministries[:-1]) if m != ministry]
        if prev:
            p["prev_ministry"] = prev
        if pooled_from:
            p["pooled_from"] = pooled_from
        renamed = sorted({names[y] for y in names} - {names[last]})
        if renamed:
            p["aka"] = renamed
        projects.append(p)

    projects.sort(key=lambda p: (p["ministry"], p.get("program", ""), p["name"]))
    for i, p in enumerate(projects):
        p["id"] = f"B{i+1:05d}"

    totals = {}
    for y in years:
        totals[str(y)] = {
            "gov": round(sum((p["years"].get(str(y), {}).get("gov") or 0) for p in projects)),
            "na": round(sum((p["years"].get(str(y), {}).get("na") or 0) for p in projects)),
        }

    out = {"notice": "", "source": raw["source"], "fetched_at": raw["fetched_at"], "unit": "억원",
           "basis": "총지출", "totals": totals, "projects": projects, "quality": []}
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    cur, prev_y = str(max(years)), str(max(years) - 1)
    new = [p for p in projects if (p["years"].get(cur, {}).get("gov") or 0) >= 100
           and not (p["years"].get(prev_y, {}).get("na") or 0) > 0]
    gone = [p for p in projects if (p["years"].get(prev_y, {}).get("na") or 0) >= 100
            and not (p["years"].get(cur, {}).get("gov") or 0) > 0]
    print(f"저장 {OUT}: 사업 {len(projects)}개 (원자료 {len(raw['rows'])}행)")
    print(f"  소관 변경으로 연결: {sum(1 for p in projects if 'prev_ministry' in p)}개, "
          f"일괄계상 표기 정리: {sum(1 for p in projects if 'pooled_from' in p)}개")
    print(f"  {cur} 신규(100억↑): {len(new)}개, {prev_y} 대비 미편성(100억↑): {len(gone)}개")
    for y, t in totals.items():
        print(f"  {y}: 정부안 {t['gov']/10000:,.1f}조, 국회확정 {t['na']/10000:,.1f}조")


if __name__ == "__main__":
    main(sys.argv[1])
