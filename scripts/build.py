"""data/budget.json -> data/budget.js (file:// 에서도 열리도록 전역 변수로 감쌈)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = ROOT / "data" / "budget.json"
dst = ROOT / "data" / "budget.js"
data = json.loads(src.read_text(encoding="utf-8"))
dst.write_text("window.BUDGET = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
print("wrote", dst)
