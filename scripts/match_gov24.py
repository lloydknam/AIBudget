"""정부24 공공서비스 ↔ 열린재정 세부사업 매칭 → data/benefit_map.json, data/benefit_review.csv

같은 소관부처 안에서 서비스명과 세부사업명(+단위사업·프로그램명)의
글자 2-gram 포함도로 후보 3개를 고른다.

상태
  auto      점수 0.9 이상 → 자동 연결
  confirmed data/benefit_overrides.json 에서 사람이 확정 (pid)
  rejected  같은 파일에서 "" 로 지정 → 연결 안 함
  review    0.6~0.9 → 화면에는 연결하지 않고 검수표에만 올림
"""
import csv, json, os, re, sys
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..")
P = lambda *a: os.path.join(ROOT, *a)
G = json.load(open(P("data", "gov24.json"), encoding="utf-8"))
B = json.load(open(P("data", "budget.json"), encoding="utf-8"))
OV_PATH = P("data", "benefit_overrides.json")
OV = json.load(open(OV_PATH, encoding="utf-8")) if os.path.exists(OV_PATH) else {}
OV = {k: v for k, v in OV.items() if not k.startswith("_")}

STOP = re.compile(r"(지원사업|지원|사업|운영|서비스|제도|및|등|의)")
AUTO, LOW = 0.9, 0.6


def norm(s):
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s or "")
    s = STOP.sub("", s)
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s)


def grams(s):
    s = norm(s)
    return {s[i:i + 2] for i in range(len(s) - 1)} or ({s} if s else set())


def sim(a, b):
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def latest(p):
    ys = sorted(p.get("years", {}))
    return (p["years"][ys[-1]].get("gov") or 0) if ys else 0


by_min = defaultdict(list)
for p in B["projects"]:
    if latest(p) > 0:
        by_min[p["ministry"]].append((p, grams(p["name"]), grams(p.get("activity")), grams(p.get("program"))))
PID = {p["id"]: p for p in B["projects"]}

out, rows, central = {}, [], 0
stat = defaultdict(int)
for s in G["services"]:
    cands = by_min.get(s.get("org"))
    if cands is None:
        continue
    central += 1
    g = grams(s["name"])
    scored = sorted(((max(sim(g, gn), 0.85 * sim(g, ga), 0.7 * sim(g, gp)), latest(p), p) for p, gn, ga, gp in cands),
                    key=lambda x: (-x[0], -x[1]))[:3]
    top = [(round(sc, 2), p) for sc, _, p in scored if sc > 0]
    sid = s["id"]
    if sid in OV:
        pid = OV[sid]
        if pid and pid in PID:
            out[sid] = {"pid": pid, "score": 1.0, "st": "confirmed"}; stat["confirmed"] += 1
        else:
            stat["rejected"] += 1
        continue
    if top and top[0][0] >= AUTO:
        out[sid] = {"pid": top[0][1]["id"], "score": top[0][0], "st": "auto"}; stat["auto"] += 1
    elif top and top[0][0] >= LOW:
        stat["review"] += 1
        rows.append([sid, s["org"], s["name"]] + sum([[p["id"], p["name"], sc] for sc, p in top], []))

json.dump({"auto": AUTO, "central": central, "stat": dict(stat), "map": out},
          open(P("data", "benefit_map.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
with open(P("data", "benefit_review.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["서비스ID", "부처", "서비스명", "후보1_ID", "후보1", "점수1", "후보2_ID", "후보2", "점수2", "후보3_ID", "후보3", "점수3"])
    w.writerows(rows)
print(f"예산 부처명과 같은 서비스 {central}건: 자동 {stat['auto']}, 확정 {stat['confirmed']}, "
      f"제외 {stat['rejected']}, 검수 대기 {stat['review']}")
