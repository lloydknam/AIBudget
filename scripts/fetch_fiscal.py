"""열린재정 재정상세통계 → 주요분석 카드 자료 (data/fiscal/*.json)

열린재정 재정상세통계 화면이 쓰는 조회(gridDataLoad.do)를 그대로 호출해 요약한다.
  - supp.json       세출 세부사업 예산편성현황(추경포함)
  - exec_month.json 월별 지출집행상황(단위사업별)
  - debt_plan.json  국가채무(D1), 월별 국가채무(중앙정부), 의무·재량지출규모추이, 중기 재정수지 전망, 중기 재정지출 계획
인증키는 필요 없다. 해외 IP에서 막히면 오류로 끝난다(기존 파일은 그대로 둔다).
"""
import json, os, re, sys, datetime, urllib.request, http.cookiejar
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "data", "fiscal")
BASE = "https://www.openfiscaldata.go.kr"
DS = {  # 이름: (odtId, dsId, 서비스 순번)
    "supp": ("6LL3V46VU0YS14H3EK67K2M8F", "VW_OPFI944", "1"),
    "exec": ("BNED1VXEB643Y775E75O0R76R", "VW_OPFI183", "1"),
    "bal":  ("388T035580BUGEUIZK0B8S32X", "VW_OPFB141", "1"),
    "exp":  ("4T3MD406N3C52D2448JWR6173", "VW_OPFB140", "1"),
    "mand": ("3CI1223X5YVY182YYL370GPO1", "TB_OPFI142", "1"),
    "debtm": ("R83QZS6DVFIK6JV36NP614173", "TB_OPFI174", "1"),
    "debt": ("11UN000D6M7UJ2LFRO76OG35Y", "TB_OPFI187", "1"),
}
TODAY = datetime.date.today().isoformat()

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [("User-Agent", "Mozilla/5.0 (aibudget fiscal fetch)"), ("Referer", BASE + "/op/ko/sd/UOPKOSDA01")]


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with opener.open(req, timeout=180) as r:
        raw = r.read().decode("utf-8", "replace")
    if raw.lstrip().startswith("<"):
        raise RuntimeError("JSON 대신 HTML 응답 (접속 차단 가능성): " + re.sub(r"<[^>]+>|\s+", " ", raw)[:160])
    return json.loads(raw)


def load(key, **cond):
    odt, ds, seq = DS[key]
    body = {"odtId": odt, "dsId": ds, "rlsSvTyCd": "S", "odtSvSeq": seq, "totalCnt": "0", "pageIndex": "1",
            "pageSize": "100000", "pageTotCnt": "0", "traDataFextNm": "DATA", "selectWon": "", "decimalPointLevel": "0", "odtNm": ""}
    body.update(cond)
    rows = post("/op/fa/sm/service/preview/rowSheet/gridDataLoad.do", body)
    if not isinstance(rows, list):
        raise RuntimeError(f"{key}: 예상과 다른 응답")
    print(f"{key}: {len(rows):,}행")
    return rows


num = lambda x: float(x or 0)


def build_supp():
    rows = [r for r in load("supp") if r.get("FIN_DE_EP_NM") == "일반지출"]
    E = lambda x: round(num(x) / 1e5)  # 천원 → 억원
    years = sorted({r["FSCL_YY"] for r in rows}, reverse=True)[:2]
    res = {}
    for y in years:
        yr = [r for r in rows if r["FSCL_YY"] == y]
        last = max(int(r["SBUDG_DGR"]) for r in yr)
        if last == 0:
            continue
        P, M = {}, {}
        for r in yr:
            if int(r["SBUDG_DGR"]) != last:
                continue
            b, a = E(r["Y_YY_DFN_KCUR_AMT"]), E(r["Y_YY_DFN_MEDI_KCUR_AMT"])
            p = P.setdefault((r["OFFC_NM"], r["SACTV_NM"]), [r["OFFC_NM"], r["SACTV_NM"], 0, 0]); p[2] += b; p[3] += a
            m = M.setdefault(r["OFFC_NM"], [r["OFFC_NM"], 0, 0]); m[1] += b; m[2] += a
        ps = list(P.values())
        res[y] = {"g": last, "b": sum(p[2] for p in ps), "a": sum(p[3] for p in ps), "c": sum(1 for p in ps if p[3] != p[2]),
                  "u": sorted([p for p in ps if p[3] > p[2]], key=lambda p: p[2] - p[3])[:12],
                  "w": sorted([p for p in ps if p[3] < p[2]], key=lambda p: p[3] - p[2])[:12],
                  "m": sorted([m for m in M.values() if m[2] != m[1]], key=lambda m: -abs(m[2] - m[1]))[:12]}
    return {"title": "추경 포함 세부사업 예산", "source": "열린재정 재정상세통계 · 세출 세부사업 예산편성현황(추경포함)", "unit": "억원",
            "basis": "일반·특별회계 일반지출(내부거래·보전지출 제외), 본예산 국회 확정 대비 최종 추경 국회 확정", "fetched_at": TODAY, "years": res}


X = re.compile(r"여유자금|예치|예탁|전출|전입|차입금|상환|내부거래|보전|이자|녹색금융|통화금융")


def build_exec():
    rows = [r for r in load("exec") if not X.search(r.get("ACTV_NM") or "")]
    E = lambda x: round(num(x) / 1e8)  # 원 → 억원
    ys = sorted({r["FSCL_YY"] for r in rows}, reverse=True)[:3]
    by = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        if r["FSCL_YY"] in ys:
            k = by[(r["FSCL_YY"], r["EXE_M"])]; k[0] += num(r["ANEXP_BDG_CAMT"]); k[1] += num(r["THISM_AGGR_EP_AMT"])
    curve = {y: [round(by[(y, f"{m:02d}")][1] / by[(y, f"{m:02d}")][0] * 100, 1) if by[(y, f"{m:02d}")][0] else None for m in range(1, 13)] for y in sorted(ys)}
    y0 = ys[0]; m0 = max(r["EXE_M"] for r in rows if r["FSCL_YY"] == y0)
    L = [r for r in rows if r["FSCL_YY"] == y0 and r["EXE_M"] == m0]

    def agg(key):
        o = {}
        for r in L:
            x = o.setdefault(r[key], [r[key], 0, 0]); x[1] += E(r["ANEXP_BDG_CAMT"]); x[2] += E(r["THISM_AGGR_EP_AMT"])
        return list(o.values())
    low = sorted([[r["OFFC_NM"], r["ACTV_NM"], E(r["ANEXP_BDG_CAMT"]), E(r["THISM_AGGR_EP_AMT"])] for r in L
                  if E(r["ANEXP_BDG_CAMT"]) >= 3000 and "거래" not in r["ACTV_NM"] and r["ACTV_NM"] != "예비비"], key=lambda x: x[3] / x[2])[:10]
    return {"title": "월별 지출집행 진도", "source": "열린재정 재정상세통계 · 월별 지출집행상황(단위사업별)", "unit": "억원",
            "basis": "예산현액 대비 누계 집행액. 여유자금운용·예탁·전출입·차입금 상환 등 금융·내부거래 단위사업 제외", "fetched_at": TODAY,
            "last": f"{y0}-{m0}", "b": sum(E(r["ANEXP_BDG_CAMT"]) for r in L), "e": sum(E(r["THISM_AGGR_EP_AMT"]) for r in L),
            "curve": curve, "fld": sorted(agg("FLD_NM"), key=lambda x: -x[1]), "mins": sorted(agg("OFFC_NM"), key=lambda x: -x[1])[:15], "low": low}


def build_debt():
    d = sorted(load("debt"), key=lambda r: r["OJ_YY"])[-12:]
    dm = sorted(load("debtm"), key=lambda r: (r["OJ_YY"], r["OJ_M"]))[-21:]
    mand = defaultdict(lambda: [0.0, 0.0])
    for r in load("mand"):
        if r.get("BC_DIV_CD_NM") == "결산" and r.get("BDG_EP_DIV_NM") in ("의무지출", "재량지출"):
            mand[r["ACNT_YR"]][0 if r["BDG_EP_DIV_NM"] == "의무지출" else 1] += num(r["EP_AMT"])
    mand = {y: [round(a / 1e12, 1), round(b / 1e12, 1)] for y, (a, b) in sorted(mand.items())[-10:]}
    plan = {}
    for key in ("bal", "exp"):
        rows = load(key); py = max(r["ACNT_YR"] for r in rows)
        plan[key] = [[re.sub(r"^[\s▣※①②o]+", "", r["DIV_ATC_NM"]).strip(), r.get("TSBDG_AMT"), r.get("THY_AF_Y1_PLAN"), r.get("THY_AF_Y2_PLAN"), r.get("THY_AF_Y3_PLAN"), r.get("THY_AF_Y4_PLAN")]
                     for r in rows if r["ACNT_YR"] == py and r.get("TSBDG_AMT") is not None]
        plan["year"] = py
    py = int(plan["year"])
    pick = lambda rows, names: [r for r in rows if r[0] in names]
    bal = [r for r in plan["bal"]]
    for i, r in enumerate(bal):  # "(GDP대비, %)" 행에 앞 행 이름을 붙인다
        if r[0].startswith("(GDP"):
            r[0] = bal[i - 1][0] + " GDP대비(%)"
    return {"title": "국가채무·의무지출·중기재정계획",
            "source": "열린재정 재정상세통계 · 국가채무(D1), 월별 국가채무(중앙정부), 의무·재량지출규모추이, 중기 재정수지 전망, 중기 재정지출 계획",
            "unit": "조원", "fetched_at": TODAY,
            "debt": [[r["OJ_YY"], r.get("GOD_SUM_AMT"), r.get("GOD_GDP_CMPRT"), r.get("CENTRAL_DEPT_AMT"), r.get("LOCAL_DEPT_AMT")] for r in d],
            "debt_m": [[f'{r["OJ_YY"]}-{r["OJ_M"]}', r.get("GOD_SUM_AMT")] for r in dm],
            "mand": mand, "plan_year": str(py), "plan_cols": [f"{py} 본예산"] + [str(py + i) for i in range(1, 5)],
            "plan_bal": bal, "plan_exp": pick(plan["exp"], {"재정지출", "예산지출", "기금지출", "의무지출", "재량지출"})}


def main():
    opener.open(BASE + "/op/ko/sd/UOPKOSDA01", timeout=60).read()  # 세션 쿠키
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("supp.json", build_supp), ("exec_month.json", build_exec), ("debt_plan.json", build_debt)):
        data = fn()
        json.dump(data, open(os.path.join(OUT, name), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        print("저장:", name)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"수집 실패: {e}")
