"""정부24 공공서비스(혜택) 정보 수집 → data/gov24.json

출처: 행정안전부_대한민국 공공서비스(혜택) 정보 (공공데이터포털 15113968)
  GET https://api.odcloud.kr/api/gov24/v3/serviceList        목록
  GET https://api.odcloud.kr/api/gov24/v3/supportConditions  지원조건(JA 코드)

인증키: 환경변수 DATA_GO_KR_KEY (공공데이터포털 '일반 인증키(Decoding)')
GitHub Actions 에서만 돌린다 (.github/workflows/gov24.yml).
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

BASE = "https://api.odcloud.kr/api/gov24/v3/"
KEY = os.environ.get("DATA_GO_KR_KEY", "").strip()
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "gov24.json")
PER = 1000

# 지원조건 코드 → 짧은 이름 (API 명세 supportConditions_model 기준)
COND = {
    "JA0101": "남성", "JA0102": "여성",
    "JA0201": "중위50이하", "JA0202": "중위51-75", "JA0203": "중위76-100",
    "JA0204": "중위101-200", "JA0205": "중위200초과",
    "JA0301": "예비부모·난임", "JA0302": "임산부", "JA0303": "출산·입양",
    "JA0313": "농업인", "JA0314": "어업인", "JA0315": "축산업인", "JA0316": "임업인",
    "JA0317": "초등학생", "JA0318": "중학생", "JA0319": "고등학생", "JA0320": "대학생·대학원생",
    "JA0326": "근로자", "JA0327": "구직자·실업자",
    "JA0328": "장애인", "JA0329": "국가보훈대상자", "JA0330": "질병·질환자",
    "JA0401": "다문화가족", "JA0402": "북한이탈주민", "JA0403": "한부모·조손",
    "JA0404": "1인가구", "JA0411": "다자녀", "JA0412": "무주택", "JA0413": "신규전입",
    "JA0414": "확대가족",
    "JA1101": "예비창업자", "JA1102": "영업중", "JA1103": "생계곤란·폐업예정",
    "JA1201": "음식점업", "JA1202": "제조업(소상공인)", "JA1299": "기타업종(소상공인)",
    "JA2101": "중소기업", "JA2102": "사회복지시설", "JA2103": "기관·단체",
    "JA2201": "제조업(기업)", "JA2202": "농림어업(기업)", "JA2203": "정보통신업(기업)",
    "JA2299": "기타업종(기업)",
}
# '해당사항없음' 코드 — 켜져 있으면 그 묶음은 누구나 통과
NONE = {"JA0322": "직업·생애", "JA0410": "가구"}


def get(path, page):
    q = urllib.parse.urlencode({"page": page, "perPage": PER, "returnType": "JSON", "serviceKey": KEY})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(BASE + path + "?" + q, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # 일시 오류 재시도
            if attempt == 3:
                raise
            print(f"  retry {path} p{page}: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))


def fetch_all(path):
    rows, page = [], 1
    while True:
        d = get(path, page)
        rows += d.get("data", [])
        total = d.get("totalCount") or d.get("matchCount") or 0
        print(f"{path} p{page}: {len(rows)}/{total}")
        if not d.get("data") or len(rows) >= total:
            return rows
        page += 1
        time.sleep(0.3)


def clip(s, n):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def main():
    if not KEY:
        sys.exit("DATA_GO_KR_KEY 가 없습니다")
    services = fetch_all("serviceList")
    conds = {c["서비스ID"]: c for c in fetch_all("supportConditions")}

    out = []
    for s in services:
        sid = s.get("서비스ID")
        c = conds.get(sid, {})
        on = [k for k in COND if str(c.get(k) or "").upper() == "Y"]
        rec = {
            "id": sid,
            "name": s.get("서비스명"),
            "org": s.get("소관기관명"),
            "orgType": s.get("소관기관유형"),
            "dept": s.get("부서명"),
            "user": s.get("사용자구분"),
            "field": s.get("서비스분야"),
            "type": s.get("지원유형"),
            "summary": clip(s.get("서비스목적요약"), 160),
            "target": clip(s.get("지원대상"), 400),
            "criteria": clip(s.get("선정기준"), 300),
            "content": clip(s.get("지원내용"), 400),
            "apply": clip(s.get("신청방법"), 160),
            "deadline": clip(s.get("신청기한"), 80),
            "url": s.get("상세조회URL"),
            "views": s.get("조회수"),
            "updated": s.get("수정일시"),
        }
        if c:
            lo, hi = num(c.get("JA0110")), num(c.get("JA0111"))
            rec["cond"] = {
                "age": [lo if lo and lo > 0 else None, hi if hi is not None and hi < 100 else None],
                "on": on,
                "none": [NONE[k] for k in NONE if str(c.get(k) or "").upper() == "Y"],
            }
        out.append(rec)

    kst = timezone(timedelta(hours=9))
    doc = {
        "source": "행정안전부_대한민국 공공서비스(혜택) 정보 (공공데이터포털 15113968)",
        "fetched_at": datetime.now(kst).strftime("%Y-%m-%d %H:%M KST"),
        "codes": COND,
        "count": len(out),
        "services": out,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"saved {len(out)} services, {sum(1 for r in out if 'cond' in r)} with conditions → {OUT}")


if __name__ == "__main__":
    main()
