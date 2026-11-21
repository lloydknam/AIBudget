"""국민혜택 탭용 자료 → data/benefits.json, data/benefits_local/*.json (시도별)

정부24 공공서비스 중 전국 대상(중앙행정기관·공공기관)만 골라 화면에 필요한 항목만 남긴다.
  - 지원조건 코드(나이·성별·소득·생애/직업·가구·사업자)
  - 예산 연결: data/benefit_map.json (auto, confirmed)
  - 생애주기: 복지로 중앙부처 복지서비스(data/bokjiro.json)와 서비스명이 같으면 그 분류를 붙인다
"""
import json, os, re
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..")
P = lambda *a: os.path.join(ROOT, *a)
G = json.load(open(P("data", "gov24.json"), encoding="utf-8"))
M = json.load(open(P("data", "benefit_map.json"), encoding="utf-8"))["map"]
BK = json.load(open(P("data", "bokjiro.json"), encoding="utf-8")) if os.path.exists(P("data", "bokjiro.json")) else {"services": []}

key = lambda s: re.sub(r"[^0-9A-Za-z가-힣]", "", s or "")
life = {}
for b in BK["services"]:
    life[(b["org"], key(b["name"]))] = b["life"]
    life.setdefault((None, key(b["name"])), b["life"])

USER = {"개인": "P", "가구": "H", "소상공인": "S", "법인/시설/단체": "C"}


def clip(s, n):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


# ---- 지역 판정 (지자체·교육청·지방 출연기관) ----
SIDO = sorted({s["org"] for s in G["services"] if s.get("orgType") == "광역시도"})
ALIAS = {"서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시", "대전": "대전광역시",
         "울산": "울산광역시", "세종": "세종특별자치시", "경기": "경기도", "강원": "강원특별자치도", "충북": "충청북도",
         "충남": "충청남도", "전북": "전북특별자치도", "전남": "전남광주통합특별시", "광주": "전남광주통합특별시",
         "경북": "경상북도", "경남": "경상남도", "제주": "제주특별자치도"}
for x in SIDO:
    ALIAS[x] = x
SGG = defaultdict(set)  # 시도 → 시군구
for s in G["services"]:
    if s.get("orgType") == "시군구" and " " in s["org"]:
        a, b = s["org"].split(" ", 1)
        SGG[a].add(b)
short = lambda n: n[:-1] if len(n) >= 3 and n[-1] in "시군구" else n


def region(s):
    t, o = s.get("orgType"), s.get("org") or ""
    if t == "광역시도":
        return o, ""
    if t == "시군구" and " " in o:
        return tuple(o.split(" ", 1))
    if t == "교육청":
        return o.replace("교육청", ""), ""
    if t in ("지방출자_출연기관", "지방공기업"):
        hits = sorted(((o.find(k), ALIAS[k]) for k in ALIAS if k in o), key=lambda x: x[0])
        sido = hits[0][1] if hits else None
        pool = [(sd, g) for sd in ([sido] if sido else SGG) for g in SGG[sd] if short(g) in o]
        pool = list({(sd, g) for sd, g in pool})
        if len(pool) == 1:
            return pool[0]
        if sido:
            return sido, ""
    return None


out, local = [], defaultdict(list)
for s in G["services"]:
    nat = s.get("orgType") in ("중앙행정기관", "공공기관")
    reg = None if nat else region(s)
    if not nat and not reg:
        continue
    c = s.get("cond") or {}
    none = c.get("none", [])
    r = {
        "i": s["id"], "n": s["name"], "o": s["org"], "t": s.get("type") or "",
        "u": "".join(USER[x] for x in (s.get("user") or "").split("||") if x in USER),
        "f": s.get("field") or "",
        "s": clip(s.get("summary"), 90), "g": clip(s.get("target"), 180), "c": clip(s.get("content"), 180),
        "d": clip(s.get("deadline"), 40), "url": s.get("url") or "",
        "a": c.get("age", [None, None]),
        "k": [k[2:] for k in c.get("on", [])],
        "z": (1 if "직업·생애" in none else 0) | (2 if "가구" in none else 0),
        "v": int(s.get("views") or 0),
    }
    m = M.get(s["id"])
    if m:
        r["p"] = m["pid"]
    lf = life.get((s["org"], key(s["name"]))) or life.get((None, key(s["name"])))
    if lf:
        r["l"] = lf
    if nat:
        out.append(r)
    else:
        r["r"] = reg[1]
        local[reg[0]].append(r)

out.sort(key=lambda r: -r["v"])
json.dump({"source": G["source"], "fetched_at": G["fetched_at"], "count": len(out), "items": out},
          open(P("data", "benefits.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
os.makedirs(P("data", "benefits_local"), exist_ok=True)
idx = []
for n, sido in enumerate(SIDO):
    items = sorted(local.get(sido, []), key=lambda r: -r["v"])
    cnt = defaultdict(int)
    for r in items:
        cnt[r["r"]] += 1
    json.dump({"sido": sido, "items": items}, open(P("data", "benefits_local", f"{n}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    idx.append({"sido": sido, "file": f"{n}.json", "n": len(items), "all": cnt.get("", 0),
                "sgg": {g: cnt.get(g, 0) for g in sorted(SGG.get(sido, []))}})
json.dump({"fetched_at": G["fetched_at"], "sido": idx}, open(P("data", "benefits_local", "index.json"), "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"지역: {sum(x['n'] for x in idx)}건 / 시도 {len(idx)}곳")
print(f"benefits.json: {len(out)}건, 예산 연결 {sum(1 for r in out if 'p' in r)}건, 생애주기 {sum(1 for r in out if 'l' in r)}건")
