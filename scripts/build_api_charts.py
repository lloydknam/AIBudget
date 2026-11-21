"""열린재정 OPEN API 목록 카드 → 그래프용 요약 자료 (data/fiscal/catalog/*.json)

주요분석 하단의 OPEN API 목록(data/openfiscal_api.json) 항목마다
열린재정 재정상세통계의 같은 이름 통계를 찾아 그래프에 쓸 만큼만 줄여 저장한다.
  - trend : 연도별 추이 (행이 적으면 구분별 계열, 많으면 연도 합계)
  - parts : 최근 연도 구성 (가장 알맞은 구분 열 기준 합계)
  - table : 최근 행 일부
인증키 불필요. GitHub Actions에서 실행한다.
"""
import json, os, re, sys, datetime, urllib.request, http.cookiejar
from collections import defaultdict, OrderedDict

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "data", "fiscal", "catalog")
BASE = "https://www.openfiscaldata.go.kr"
PAGE = 60000
TODAY = datetime.date.today().isoformat()

jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
op.addheaders = [("User-Agent", "Mozilla/5.0 (aibudget catalog)"), ("Referer", BASE + "/op/ko/sd/UOPKOSDA01")]


def post(path, body, timeout=240):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with op.open(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    if raw.lstrip().startswith("<"):
        raise RuntimeError("HTML 응답")
    return json.loads(raw)


# 행 키와 머리글 키가 다를 때 쓰는 기본 이름
KNOWN = {"FSCL_YY": "회계연도", "ACNT_YR": "회계연도", "OJ_YY": "기준년도", "TRGT_YR": "기준년도", "OJ_M": "기준월", "EXE_M": "집행월",
         "OFFC_NM": "소관", "FSCL_NM": "회계", "ACCT_NM": "계정", "FLD_NM": "분야", "SECT_NM": "부문", "PGM_NM": "프로그램",
         "ACTV_NM": "단위사업", "SACTV_NM": "세부사업", "CITM_NM": "목", "EITM_NM": "세목", "IKWAN_NM": "관", "IHANG_NM": "항", "IMOK_NM": "목"}
SKIP = re.compile(r"^(PAGE_TOT_CNT|PAGE_ROW_NUM|RN|FRST_REG.*|LAST_MDFCN.*)$|_CD$|_NO$")
YEAR = re.compile(r"(^|_)(YY|YR|YEAR)$|연도|년도")


def norm(s):
    s = re.sub(r"\(OPEN API\)", "", s or "")
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s)


def names_for(rows, head):
    hid = {h.get("ognDsColId"): h.get("colNm") or h.get("dpColHgNm") for h in head if h.get("ognDsColId")}
    keys = [k for k in rows[0].keys() if not SKIP.search(k)] if rows else []
    out = OrderedDict()
    for k in keys:
        if k in hid:
            out[k] = hid[k]; continue
        if k in KNOWN:
            out[k] = KNOWN[k]; continue
        tk = set(k.split("_")) - {"AMT", "NM", "CD"}
        best, score = None, 0
        for h, n in hid.items():
            s = len(tk & set(h.split("_")))
            if s > score:
                best, score = n, s
        out[k] = best if best and score >= 2 else k
    return out


def isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def reduce(rows, head, total):
    cols = names_for(rows, head)
    if not rows or not cols:
        return None
    ycol = next((k for k, n in cols.items() if YEAR.search(k) or YEAR.search(n or "")), None)
    mcol = next((k for k, n in cols.items() if k != ycol and (re.search(r"(^|_)(M|MM)$", k) or re.search(r"(집행|기준)월$", n or ""))), None)
    nums = [k for k in cols if k not in (ycol, mcol) and sum(isnum(r.get(k)) for r in rows[:500]) >= 0.8 * sum(r.get(k) is not None for r in rows[:500]) > 0]
    dims = [k for k in cols if k not in nums and k not in (ycol, mcol)]
    card = {k: len({r.get(k) for r in rows}) for k in dims}
    nums = nums[:8]
    res = {"cols": {k: cols[k] for k in ([ycol] if ycol else []) + ([mcol] if mcol else []) + dims + nums},
           "nums": nums, "year": ycol, "month": mcol, "total": total, "got": len(rows)}
    years = sorted({str(r.get(ycol)) for r in rows if r.get(ycol) is not None}) if ycol else []
    if ycol and total > len(rows) and len(years) > 1:
        years = years[1:]  # 잘렸을 수 있는 가장 오래된 연도 제외
    last = years[-1] if years else None
    L = [r for r in rows if not ycol or str(r.get(ycol)) == last]
    if mcol and L:
        lm = max(str(r.get(mcol)) for r in L)
        L = [r for r in L if str(r.get(mcol)) == lm]
        res["last_month"] = lm
    res["last"] = last
    # 추이
    if ycol and len(years) >= 2 and nums:
        lastm = {}
        if mcol:
            for r in rows:
                y = str(r.get(ycol)); lastm[y] = max(lastm.get(y, ""), str(r.get(mcol)))
        per = defaultdict(list)
        for r in rows:
            y = str(r.get(ycol))
            if y in years and (not mcol or str(r.get(mcol)) == lastm[y]):
                per[y].append(r)
        mx = max(len(v) for v in per.values())
        label = next((d for d in dims if 1 < card[d] <= 15), None)
        if mx <= 15 and label:   # 연도마다 몇 줄: 구분별 계열
            labs = list(OrderedDict.fromkeys(str(r.get(label)) for r in rows if r.get(label) is not None))[:12]
            res["trend"] = {"x": years, "by": label, "series": {n: {lab: [next((r.get(n) for r in per[y] if str(r.get(label)) == lab), None) for y in years] for lab in labs} for n in nums}}
        elif mx <= 1:
            res["trend"] = {"x": years, "series": {n: {cols[n]: [next((r.get(n) for r in per[y]), None) for y in years]} for n in nums}}
        else:                    # 상세 자료: 연도 합계
            res["trend"] = {"x": years, "sum": True, "series": {n: {cols[n]: [round(sum(r.get(n) or 0 for r in per[y] if isnum(r.get(n))), 2) for y in years]} for n in nums}}
    # 구성
    pick = next((d for d in dims if 2 <= len({r.get(d) for r in L}) <= 30), None)
    if pick and nums and L:
        agg = defaultdict(lambda: [0.0] * len(nums))
        for r in L:
            a = agg[str(r.get(pick))]
            for i, n in enumerate(nums):
                if isnum(r.get(n)):
                    a[i] += r[n]
        res["parts"] = {"by": pick, "rows": sorted([[k] + [round(x, 2) for x in v] for k, v in agg.items()], key=lambda x: -abs(x[1]))[:30]}
    # 표
    show = list(res["cols"].keys())[:9]
    res["table"] = {"cols": show, "rows": [[r.get(k) for k in show] for r in L[:80]]}
    return res


def main():
    op.open(BASE + "/op/ko/sd/UOPKOSDA01", timeout=60).read()
    cat = post("/op/ko/sd/dtsStats/selectScolSrchList.do", {"opKoSdDtsStatsDVO": {"searchKeyword": "", "opeDtFrom": "", "opeDtTo": "", "dtaLoadPrdCd": "", "ofdMngOgNm": "", "ognSysNm": "", "rlsSvIxNm": ""}})
    cat = cat if isinstance(cat, list) else next(v for v in cat.values() if isinstance(v, list))
    by = {}
    for c in cat:
        m = re.search(r"S-(\d+)", c.get("rlsSvIxNm") or "")
        if m:
            by.setdefault(norm(c["odtNm"]), (c, m.group(1)))
    items = json.load(open(os.path.join(ROOT, "data", "openfiscal_api.json"), encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)
    keys = sorted(by, key=len, reverse=True)
    idx, cache, ok = {}, {}, 0
    for g in items["groups"]:
        for it in g["items"]:
            nm = norm(re.sub(r",\s*\d+\)$", ")", it["name"]))
            k = nm if nm in by else next((x for x in keys if nm.startswith(x) or x.startswith(nm)), None)
            if not k:
                idx[it["no"]] = None; continue
            c, seq = by[k]
            if c["odtId"] not in cache:
                try:
                    srv = post("/op/ko/sd/dtsStats/selectSrvDtlInfoList.do", {"opKoSdDtsStatsDVO": {"odtId": c["odtId"]}})
                    ds = srv["selectSrvDtlInfo"]["dsId"]
                    pv = post("/op/ko/sm/preview/rowSheet/getPreviewInfo.do", {"odtId": c["odtId"], "rlsSvTyCd": "S", "odtSvSeq": seq, "dsId": ds})
                    body = {"odtId": c["odtId"], "dsId": ds, "rlsSvTyCd": "S", "odtSvSeq": seq, "totalCnt": "0", "pageIndex": "1", "pageSize": str(PAGE),
                            "pageTotCnt": "0", "traDataFextNm": "DATA", "selectWon": "", "decimalPointLevel": "0", "odtNm": ""}
                    rows = post("/op/fa/sm/service/preview/rowSheet/gridDataLoad.do", body)
                    total = int(rows[0].get("PAGE_TOT_CNT") or len(rows)) if rows else 0
                    red = reduce(rows, pv.get("rowSheetHead") or [], total)
                    if red:
                        red.update({"name": c["odtNm"], "org": c.get("ofdMngOgNm"), "cls": c.get("dtaClsNm"), "cycle": c.get("dtaLoadPrdNm"), "fetched_at": TODAY})
                    cache[c["odtId"]] = red
                    print(f"{c['odtNm']}: {len(rows):,}/{total:,}행 → {'추이' if red and 'trend' in red else ''} {'구성' if red and 'parts' in red else ''}")
                except Exception as e:
                    cache[c["odtId"]] = None
                    print(f"{c['odtNm']}: 실패 {type(e).__name__} {str(e)[:80]}")
            red = cache[c["odtId"]]
            if red:
                json.dump(red, open(os.path.join(OUT, f"{it['no']}.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"), default=str)
                idx[it["no"]] = c["odtNm"]; ok += 1
            else:
                idx[it["no"]] = None
    json.dump({"fetched_at": TODAY, "ok": ok, "items": idx}, open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"그래프 자료 {ok}/{len(idx)}건")


if __name__ == "__main__":
    main()
