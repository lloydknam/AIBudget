"""정부24 공공서비스 ↔ 열린재정 세부사업 매칭 → data/benefit_map.json

같은 소관부처 안에서 서비스명과 세부사업명(+단위사업·프로그램명)의
글자 2-gram 유사도로 가장 가까운 사업을 고른다. 점수가 낮으면 미매칭.
결과의 score 는 검수용이다 (자동 매칭이라 틀린 연결이 섞일 수 있음).
"""
import json, os, re, sys
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..")
G = json.load(open(os.path.join(ROOT, "data", "gov24.json"), encoding="utf-8"))
B = json.load(open(os.path.join(ROOT, "data", "budget.json"), encoding="utf-8"))

STOP = re.compile(r"(지원사업|지원|사업|운영|서비스|제도|및|등|의)")


def norm(s):
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s or "")
    s = STOP.sub("", s)
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s)


def grams(s):
    s = norm(s)
    return {s[i:i + 2] for i in range(len(s) - 1)} or ({s} if s else set())


def sim(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))  # 짧은 쪽 기준 포함도


def latest(p):
    ys = sorted(p.get("years", {}))
    return (p["years"][ys[-1]].get("gov") or 0) if ys else 0


by_min = defaultdict(list)
for p in B["projects"]:
    if latest(p) <= 0:
        continue
    by_min[p["ministry"]].append((p, grams(p["name"]), grams(p.get("activity")), grams(p.get("program"))))

THRESH = float(os.environ.get("MATCH_THRESH", "0.6"))
out, central, matched = {}, 0, 0
miss_org = defaultdict(int)
for s in G["services"]:
    cands = by_min.get(s.get("org"))
    if cands is None:
        if s.get("orgType") == "중앙행정기관":
            miss_org[s.get("org")] += 1
        continue
    central += 1
    g = grams(s["name"])
    best, bs = None, 0.0
    for p, gn, ga, gp in cands:
        sc = max(sim(g, gn), 0.85 * sim(g, ga), 0.7 * sim(g, gp))
        if sc > bs or (sc == bs and best and latest(p) > latest(best)):
            best, bs = p, sc
    if best and bs >= THRESH:
        matched += 1
        out[s["id"]] = {"pid": best["id"], "score": round(bs, 2)}

json.dump(
    {"thresh": THRESH, "central": central, "matched": matched, "map": out},
    open(os.path.join(ROOT, "data", "benefit_map.json"), "w", encoding="utf-8"),
    ensure_ascii=False, separators=(",", ":"),
)
rate = matched / central * 100 if central else 0
print(f"부처명이 예산 부처와 같은 서비스 {central}건 중 {matched}건 매칭 ({rate:.1f}%), 기준 {THRESH}")
if miss_org:
    print("예산 부처명과 안 맞는 중앙행정기관:", dict(sorted(miss_org.items(), key=lambda x: -x[1])[:15]), file=sys.stderr)
