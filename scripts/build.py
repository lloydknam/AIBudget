"""data/budget.json -> data/budget.js (file:// 에서도 열리도록 전역 변수로 감쌈).

실데이터(source 있음)는 부처·분야 등 반복 문자열을 사전으로 압축해 파일 크기를 줄이고,
화면(index.html)이 불러올 때 원래 구조로 풉니다. 샘플 데이터는 그대로 씁니다.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = ROOT / "data" / "budget.json"
dst = ROOT / "data" / "budget.js"
data = json.loads(src.read_text(encoding="utf-8"))

if data.get("source"):
    years = sorted({int(y) for p in data["projects"] for y in p["years"]})
    keys = ["ministry", "fund", "field", "sector", "program", "activity"]
    dicts = {k: [] for k in keys}
    index = {k: {} for k in keys}

    def enc(k, v):
        v = v or ""
        if v not in index[k]:
            index[k][v] = len(dicts[k])
            dicts[k].append(v)
        return index[k][v]

    rows = []
    for p in data["projects"]:
        r = [enc(k, p.get(k)) for k in keys] + [p["name"]]
        for y in years:
            v = p["years"].get(str(y)) or {}
            r += [v.get("gov"), v.get("na")]
        extra = {k: p[k] for k in ("prev_ministry", "pooled_from", "aka") if p.get(k)}
        if extra:
            r.append(extra)
        rows.append(r)
    packed = {k: v for k, v in data.items() if k != "projects"}
    packed.update({"packed": {"keys": keys, "years": years, "dicts": dicts, "rows": rows}})
    data = packed

dst.write_text("window.BUDGET = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
               encoding="utf-8")
print("wrote", dst, f"{dst.stat().st_size/1e6:.1f}MB")
