"""복지로 중앙부처 복지서비스 목록 수집 → data/bokjiro.json

출처: 한국사회보장정보원_중앙부처복지서비스 (공공데이터포털 15090532)
  GET https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001
목록만 받는다 (약 460건, 호출 1~2회). 개발계정은 하루 100건 한도라 상세조회는 하지 않는다.
목록에 생애주기·가구유형·관심주제가 이름으로 들어 있어, 정부24 자료의 생애주기 교차 확인에 쓴다.
"""
import json, os, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"
KEY = os.environ.get("DATA_GO_KR_KEY", "").strip()
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "bokjiro.json")
ROWS = 500


def get(page):
    q = urllib.parse.urlencode({"serviceKey": KEY, "callTp": "L", "pageNo": page,
                                "numOfRows": ROWS, "srchKeyCode": "003"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(URL + "?" + q, timeout=60) as r:
                return ET.fromstring(r.read())
        except Exception as e:
            if attempt == 3:
                raise
            print(f"  retry p{page}: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))


def split(v):
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def main():
    if not KEY:
        sys.exit("DATA_GO_KR_KEY 가 없습니다")
    items, page = [], 1
    while True:
        root = get(page)
        code = root.findtext(".//resultCode")
        if code not in (None, "0", "00"):
            sys.exit(f"API 오류 {code}: {root.findtext('.//resultMessage')}")
        rows = root.findall(".//servList")
        total = int(root.findtext(".//totalCount") or 0)
        for e in rows:
            t = {c.tag: (c.text or "").strip() for c in e}
            items.append({
                "id": t.get("servId"),
                "name": t.get("servNm"),
                "org": t.get("jurMnofNm"),
                "dept": t.get("jurOrgNm"),
                "summary": t.get("servDgst"),
                "life": split(t.get("lifeArray")),
                "target": split(t.get("trgterIndvdlArray")),
                "theme": split(t.get("intrsThemaArray")),
                "cycle": t.get("sprtCycNm"),
                "provide": t.get("srvPvsnNm"),
                "online": t.get("onapPsbltYn"),
                "url": t.get("servDtlLink"),
                "views": t.get("inqNum"),
            })
        print(f"p{page}: {len(items)}/{total}")
        if not rows or len(items) >= total:
            break
        page += 1
    kst = timezone(timedelta(hours=9))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"source": "한국사회보장정보원_중앙부처복지서비스 (공공데이터포털 15090532)",
                   "fetched_at": datetime.now(kst).strftime("%Y-%m-%d %H:%M KST"),
                   "count": len(items), "services": items},
                  f, ensure_ascii=False, separators=(",", ":"))
    print(f"saved {len(items)} → {OUT}")


if __name__ == "__main__":
    main()
