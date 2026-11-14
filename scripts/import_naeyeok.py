"""열린재정 사업설명자료(HWPX)에서 뽑은 내역사업 -> data/naeyeok.json (억원).

입력: 브라우저에서 모은 naeyeok_raw.json
  [{"o": 소관, "s": 세부사업명, "a": 세부사업 정부안(백만원), "t": 표의 합계(백만원),
    "items": [{"name": 내역사업명, "amt": 백만원}], ...}, ...]
  (사업설명자료의 '구분 | 2026년 예산액 | 2027년 정부안액 | 증감' 표에서 '합계' 아래 행들)

출력: data/naeyeok.json  {"소관|세부사업명": [{"name": ..., "amt": 억원}]}
  키는 data/budget.json 의 소관·세부사업명과 같게 맞춥니다 (화면이 이 키로 찾음).

걸러내는 것:
  - 표 합계가 세부사업 정부안과 1백만원 넘게 다른 사업 (다른 표를 잘못 읽었을 수 있음)
  - 내역사업 합이 표 합계와 1백만원 넘게 다른 사업
  - budget.json 에서 같은 사업을 찾지 못한 사업

사용법: python scripts/import_naeyeok.py <naeyeok_raw.json 경로>
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUDGET = ROOT / "data" / "budget.json"
OUT = ROOT / "data" / "naeyeok.json"
POOLED = "기획예산처"
SUFFIX = re.compile(r"\(([가-힣]{1,10}(?:부|처|청|위|원|실))\)$")
YEAR = "2027"


def norm(s: str) -> str:
    s = re.sub(r"[\sㆍ·・‧∙]", "", s or "")
    return s.replace("（", "(").replace("）", ")")


def main(src: str):
    raw = json.loads(Path(src).read_text(encoding="utf-8"))
    budget = json.loads(BUDGET.read_text(encoding="utf-8"))

    # budget.json 의 (소관, 정규화 사업명) -> 사업. 2027 금액이 있는 사업만.
    index = {}
    for p in budget["projects"]:
        if (p["years"].get(YEAR) or {}).get("gov"):
            index.setdefault((p["ministry"], norm(p["name"])), []).append(p)

    out, stats = {}, Counter()
    for r in raw:
        stats["사업설명자료에서 표를 읽은 사업"] += 1
        items = [i for i in r.get("items", []) if i.get("name") and i.get("amt") is not None]
        if not items:
            stats["제외: 내역사업 행 없음"] += 1
            continue
        if abs((r.get("t") or 0) - (r.get("a") or 0)) > 1:
            stats["제외: 표 합계가 세부사업 금액과 다름"] += 1
            continue
        if abs(sum(i["amt"] for i in items) - (r.get("t") or 0)) > 1:
            stats["제외: 내역사업 합이 표 합계와 다름"] += 1
            continue
        name = (r["s"] or "").strip()
        if r["o"] == POOLED:
            m = SUFFIX.search(name)
            if m:
                name = name[: m.start()]
        cands = index.get((r["o"], norm(name)), [])
        if len(cands) != 1:
            stats["제외: budget.json 에서 못 찾음" if not cands else "제외: 같은 이름이 여러 개"] += 1
            continue
        p = cands[0]
        key = f'{p["ministry"]}|{p["name"]}'
        if key in out:      # 같은 이름이 여러 회계에 나뉜 사업: 내역사업별로 합산
            merged = {i["name"]: i["amt"] for i in out[key]}
            for i in items:
                merged[i["name"]] = round(merged.get(i["name"], 0) + i["amt"] / 100, 1)
            out[key] = [{"name": k, "amt": v} for k, v in merged.items()]
            stats["여러 회계 합산"] += 1
        else:
            out[key] = [{"name": i["name"], "amt": round(i["amt"] / 100, 1)} for i in items]
        stats["연결됨"] += 1

    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for k, v in stats.most_common():
        print(f"{v:6d}  {k}")
    n_items = sum(len(v) for v in out.values())
    multi = sum(1 for v in out.values() if len(v) > 1)
    print(f"wrote {OUT} : 세부사업 {len(out)}개, 내역사업 {n_items}개 (내역사업 2개 이상 {multi}개), {OUT.stat().st_size/1e6:.2f}MB")


if __name__ == "__main__":
    main(sys.argv[1])
