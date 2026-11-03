# 예산 AI 분석

국가 예산 세부사업을 탐색하고 심사 참고 대상을 골라 보는 개인 프로젝트입니다. 메뉴 구성은 「국가예산 AI 분석시스템 안내」 책자의 6개 메뉴(홈, 한눈에 보기, 예산 탐색, 심사 참고, 조건으로 찾기, AI에게 묻기)와 부가 메뉴(삶의 질 지표)를 참고했습니다. 공식 시스템과는 무관한 독립 구현입니다.

사이트: https://lloydknam.github.io/AIBudget/

## 데이터
- 출처: 열린재정 Open API `TotalExpenditure5` (세부사업 예산편성현황, **총지출 기준**, `BDG_FND_DIV_CD=0`, `ANEXP_INQ_STND_CD=1`)
- 연도: 2024~2027 (각 연도 정부안 `Y_YY_MEDI_KCUR_AMT`, 국회 확정 `Y_YY_DFN_MEDI_KCUR_AMT`, 원자료 단위 천원 → 화면 억원)
- 검증: 국회 확정 합계 2024 656.6조, 2025 673.3조, 2026 727.9조로 본예산 총지출과 일치. 2027 정부안 820.9조.
- 연도 간 같은 사업 연결: 띄어쓰기·가운뎃점 차이 무시, 기획예산처 일괄계상 표기 `사업명(원부처)` 정리, 이름이 같고 연도가 겹치지 않으면 소관 변경으로 보고 연결 (예: 2026 기획재정부 → 2027 재정경제부·기획예산처). 이름 자체가 바뀐 사업(예: 아동수당 → 아동기본수당)은 신규·미편성으로 남습니다.
- 아직 없음: 집행·결산(지출·이월·불용), 국회 검토보고서·사업설명자료

## 데이터 갱신 방법
열린재정 API는 해외·클라우드 IP(깃허브 Actions 포함)에서 호출하면 오류 페이지를 돌려줍니다. 그래서 **한국 IP의 브라우저**에서 받습니다.

1. 브라우저로 `https://openapi.openfiscaldata.go.kr/TotalExpenditure5?Type=json` 페이지를 연 상태에서, 같은 출처로 연도별 전체 페이지를 받아 `aibudget_data.json`으로 저장 (컬럼·사전 형식은 `scripts/import_browser.py` 참고)
2. 변환과 화면 데이터 생성:
   ```
   python scripts/import_browser.py aibudget_data.json
   python scripts/build.py
   ```
3. `data/budget.json`, `data/budget.js` 커밋

`scripts/fetch_openfiscal.py`는 한국 IP의 PC에서 직접 실행할 때 쓰는 대안 수집기입니다 (`ExpenditureBudgetInit5`, 총계 기준이라 총지출과 다름).

## 구조
- `index.html`: 단일 파일 화면 (외부 라이브러리 없음)
- `data/budget.json`: 사업별 연도별 정부안·국회 확정 (억원)
- `data/budget.js`: 화면용 압축 데이터 (`build.py`가 생성, 화면에서 풀어서 사용)
- `scripts/make_sample.py`: 화면 시험용 샘플 데이터 생성기

## 한계
- 심사 참고 규칙은 예시 기준이며 실제 심사 기준이 아닙니다.
- 조건 검색은 정해진 문장 패턴(증가율, 감소율, 금액, 부처·분야, 신규·미편성)만 해석합니다.
- AI에게 묻기는 지금은 예산 수치만 근거로 사업을 찾아 줍니다. Upstage API 키를 넣으면 요약을 만들고, 키는 저장되지 않습니다.
