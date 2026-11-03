"""샘플 데이터 생성기.

실제 예산 수치가 아닙니다. 화면 구조와 기능을 시험하기 위한 가상의 데이터입니다.
실데이터는 fetch_openfiscal.py 로 수집한 뒤 build.py 로 data/budget.json 을 만듭니다.
"""
import json
import random
from pathlib import Path

random.seed(42)
OUT = Path(__file__).resolve().parent.parent / "data" / "budget.json"

FIELDS = ["보건", "사회복지", "고용노동", "농림수산", "산업·중소기업", "교육", "문화·관광",
          "환경", "국토·수자원", "교통·물류", "공공질서·안전", "일반공공행정"]
MINISTRIES = {"보건": "보건복지부", "사회복지": "보건복지부", "고용노동": "고용노동부",
              "농림수산": "농림축산식품부", "산업·중소기업": "산업통상부", "교육": "교육부",
              "문화·관광": "문화체육관광부", "환경": "기후에너지환경부", "국토·수자원": "국토교통부",
              "교통·물류": "국토교통부", "공공질서·안전": "법무부", "일반공공행정": "행정안전부"}
NAMES = ["기초연금 지급", "아동수당 확대", "노인일자리 운영", "국민취업지원 제도", "지역의료 거점 확충",
         "스마트농업 기반 구축", "중소기업 연구개발 지원", "공교육 디지털 전환", "생활 SOC 확충",
         "재생에너지 보급", "하수도 정비", "고속도로 건설", "철도 안전 점검", "치안 인프라 개선",
         "문화시설 건립", "관광 인프라 확충", "청년 주거 지원", "전통시장 현대화", "직업훈련 바우처"]

PAGES_TEXT = [
    "사업의 필요성: 본 사업은 고령화에 따른 수요 증가에 대응하기 위한 것임 (샘플 문구)",
    "성과지표: 대상자 수 및 집행 실적을 연간 점검함 (샘플 문구)",
    "전년도 대비 증액 사유: 대상 인원 증가 및 단가 인상 반영 (샘플 문구)",
    "국회 심사 의견: 집행률 저조 사업에 대한 사유 제출 요구 (샘플 문구)",
]


def make_projects():
    projects = []
    for i in range(60):
        field = FIELDS[i % len(FIELDS)]
        base = random.randint(300, 9000)  # 억원 단위 가상값
        name = f"{random.choice(NAMES)} {i+1:02d}"
        y = {}
        cur = base
        for yr in (2023, 2024, 2025, 2026):
            y[yr] = {"gov": cur, "na": cur + random.randint(-80, 80)}
            cur = int(cur * random.uniform(0.9, 1.25))
        y[2027] = {"gov": int(cur * random.uniform(0.85, 1.4)), "na": None}
        ex = {}
        for yr in (2023, 2024, 2025):
            budget = y[yr]["na"] or y[yr]["gov"]
            rate = random.uniform(0.6, 1.0)
            spent = int(budget * rate)
            ex[yr] = {"budget": budget, "spent": spent, "unused": budget - spent,
                      "rate": round(rate * 100, 1)}
        docs = []
        for k in range(random.randint(1, 3)):
            docs.append({
                "title": f"2027 예산안 검토보고서 - {name}",
                "page": random.randint(3, 40),
                "text": random.choice(PAGES_TEXT),
            })
        projects.append({"id": f"P{i+1:03d}", "name": name, "field": field,
                         "ministry": MINISTRIES[field], "years": y, "exec": ex, "docs": docs})
    return projects


def make_quality():
    cities = ["서울 강남구", "경기 성남시", "부산 해운대구", "대구 수성구", "광주 서구",
              "대전 유성구", "세종시", "제주시", "강원 춘천시", "전북 전주시"]
    return [{"name": c, "rate": round(random.uniform(60, 98), 1),
             "income": random.randint(2800, 5200)} for c in cities]


if __name__ == "__main__":
    data = {
        "notice": "샘플 데이터입니다. 실제 예산 수치가 아닙니다.",
        "unit": "억원",
        "projects": make_projects(),
        "quality": make_quality(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT, len(data["projects"]), "projects")
