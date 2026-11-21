"""국민혜택 탭용 자료 → data/benefits.json

정부24 공공서비스 중 전국 대상(중앙행정기관·공공기관)만 골라 화면에 필요한 항목만 남긴다.
  - 지원조건 코드(나이·성별·소득·생애/직업·가구·사업자)
  - 예산 연결: data/benefit_map.json (auto, confirmed)
  - 생애주기: 복지로 중앙부처 복지서비스(data/bokjiro.json)와 서비스명이 같으면 그 분류를 붙인다
"""
import json, os, re

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


out = []
for s in G["services"]:
    if s.get("orgType") not in ("중앙행정기관", "공공기관"):
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
    out.append(r)

out.sort(key=lambda r: -r["v"])
json.dump({"source": G["source"], "fetched_at": G["fetched_at"], "count": len(out), "items": out},
          open(P("data", "benefits.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(f"benefits.json: {len(out)}건, 예산 연결 {sum(1 for r in out if 'p' in r)}건, 생애주기 {sum(1 for r in out if 'l' in r)}건")
