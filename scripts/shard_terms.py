"""desc/terms.json.gz (낱말 → 세부사업 id 목록, 6.8MB) 를 첫 글자 초성별 샤드로 나눕니다.
화면은 검색어 낱말의 초성에 해당하는 샤드 하나만 받으면 됩니다.
출력: desc/terms/<초성번호 0~18 | x>.json.gz
사용: python3 scripts/shard_terms.py   (terms.json.gz 를 먼저 만들어 두어야 함)
"""
import gzip, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "desc" / "terms.json.gz"
OUT = ROOT / "desc" / "terms"

def shard_of(token):
    c = token[0]
    code = ord(c) - 0xAC00
    if 0 <= code < 11172:                      # 한글 음절
        return str(code // 588)                # 초성 0~18
    return "x"                                 # 영문·숫자·기타

def main():
    with gzip.open(SRC, "rt", encoding="utf-8") as f:
        terms = json.load(f)
    shards = {}
    for tok, ids in terms.items():
        shards.setdefault(shard_of(tok), {})[tok] = ids
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for k, d in sorted(shards.items()):
        with gzip.open(OUT / f"{k}.json.gz", "wt", encoding="utf-8", compresslevel=9) as f:
            json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
        print(k, len(d), (OUT / f"{k}.json.gz").stat().st_size)

if __name__ == "__main__":
    main()
