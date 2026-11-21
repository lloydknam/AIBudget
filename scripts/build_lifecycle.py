# 국민혜택(생애주기) 태그 생성: 사업설명자료의 '대상' 문장에서 생애단계·상황 키워드를 찾아 data/lifecycle.json 을 만든다.
# 사용: python3 scripts/build_lifecycle.py   (저장소 루트에서 실행)
import gzip, glob, json, os, re

STAGES = {  # 생애단계 (키워드는 '대상' 문장 안에서만 본다)
    "영유아": ["영유아", "신생아", "출산", "임산부", "산모", "태아", "어린이집"],
    "아동": ["아동", "초등", "유치원", "방과후"],
    "청소년": ["청소년", "중학생", "고등학생", "중·고", "중고등"],
    "청년": ["청년", "대학생", "취업준비", "사회초년생", "구직자"],
    "신혼·육아": ["신혼", "혼인", "맞벌이", "다자녀", "한부모", "육아", "양육"],
    "중장년": ["중장년", "중년", "경력단절"],
    "노년": ["노인", "어르신", "고령", "65세", "기초연금", "노년"],
}
SITUATIONS = {  # 상황 칩 (여러 개 가능)
    "저소득": ["기초생활", "저소득", "차상위", "수급자", "생계급여", "의료급여"],
    "장애": ["장애인", "장애아동"],
    "주거": ["주거", "임대", "전세", "주택 구입", "주택구입"],
    "돌봄": ["돌봄", "돌봄서비스", "아이돌봄", "방과후"],
    "일자리": ["일자리", "취업", "고용", "직업훈련", "훈련"],
    "건강": ["건강보험", "의료비", "건강검진", "예방접종"],
}

def block_text(rec):
    out = []
    bl = rec.get("blocks") or []
    parts = [x.get("b", []) for x in bl] if bl and isinstance(bl[0], dict) and "file" in bl[0] else [bl]
    for arr in parts:
        for b in arr:
            if isinstance(b, str):
                out.append(b)
            elif isinstance(b, dict) and b.get("tbl"):
                for row in b["tbl"]:
                    out.append(" ".join(c for c in row if c and c.strip()))
    return out

def target_windows(lines):
    # '대상' 주변 120자만 본다 (표 전체·법령 문장을 읽으면 무관한 키워드가 섞인다)
    wins = []
    for ln in lines:
        for m in re.finditer("대상", ln):
            wins.append(ln[max(0, m.start() - 20):m.start() + 120])
    return " ".join(wins)

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out, review = {}, []
    for f in sorted(glob.glob(os.path.join(root, "desc", "B*.json.gz"))):
        for rec in [json.load(gzip.open(f, "rt", encoding="utf-8"))]:
            pid = rec.get("id")
            if not pid:
                continue
            win = target_windows(block_text(rec))
            if not win:
                continue
            st = [k for k, kws in STAGES.items() if any(w in win for w in kws)]
            si = [k for k, kws in SITUATIONS.items() if any(w in win for w in kws)]
            if st or si:
                out[pid] = {"s": st, "t": si, "n": rec.get("name", "")}
    # 검수용: 단계 태그가 없는 것은 목록에서 빠진다. 개수만 출력
    for k in STAGES:
        print(k, sum(1 for v in out.values() if k in v["s"]))
    path = os.path.join(root, "data", "lifecycle.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    print("tagged", len(out), "->", path)

if __name__ == "__main__":
    main()
