# Wildfire Agent Web MVP Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 위치 입력 기반으로 산불 위험 분석, 오탐 교정, 대응 가이드를 제공하는 배포 가능한 에이전트 AI 웹 서비스를 구축한다.

**Architecture:** 프론트엔드는 Next.js로 지도/입력/리포트 UX를 담당하고, 백엔드는 FastAPI + Python으로 데이터 전처리, 위험도 계산, LangGraph 에이전트 루프, 보고서 생성 API를 제공한다. 1차 MVP는 24시간 상시 모니터링을 버리고 **사용자 위치 입력 → 데이터 조회/정규화 → 위험도 계산 → 에이전트 검토 → 행동 가이드 반환** 흐름에 집중한다.

**Tech Stack:** Next.js 15 + TypeScript + Tailwind + MapLibre, FastAPI + Pydantic + Pandas + scikit-learn + LangGraph, SQLite/Postgres(초기 SQLite 가능), Docker, Vercel(프론트) + Railway/Render/Fly.io(백엔드)

---

## 1. 현재 확인된 컨텍스트

### 작업 공간
- Workspace: `/Users/leeseungwoo/Desktop/yoonity/4. 산림청 공모전/project`
- Data/Materials: `/Users/leeseungwoo/Desktop/yoonity/4. 산림청 공모전`
- 현재 workspace는 사실상 비어 있음 (`.hermes/`만 존재)

### 데이터 샘플에서 확인한 점
- 원천데이터 샘플은 `raw_data_info.fire_info`, `source_data_info.user_info`, `weather_conditions`, `terrain_conditions`, `fuel_conditions`, `Infra_Social`, `occurrence_status`를 포함
- 라벨데이터는 단순 정답 클래스가 아니라 `query`, `tree_of_thought`, branch-level reasoning, confidence score를 포함
- 샘플 280건 기준 라벨 쿼리 유형 분포:
  - conditional 41
  - sequential 40
  - composite 38
  - hypothetical 37
  - probability 37
  - comparative 36
- 샘플 280건 기준 목적 분포 상위:
  - 시간예측 39
  - 현황파악 33
  - 위험평가 30
  - 대응전략 29
  - 경과예측 29
  - 피해예측 28
  - 의사결정 27
- 즉, 이 데이터는 **단순 산불 탐지 모델**보다 **상황판단 + 설명 + 의사결정 지원** 웹서비스에 더 적합함

### 제품 모드 판단
이 프로젝트는 아래 3가지를 모두 포함할 수 있지만, MVP의 1차 모드는 다음으로 고정한다.

**Primary MVP mode: decision-support / agentic risk analysis**

즉,
- 탐지 모델 자체를 새로 SOTA로 훈련하는 프로젝트가 아니라
- 위치/상황 입력을 받아
- 산불 위험 및 오탐 가능성을 분석하고
- 사람이 바로 행동 가능한 대응 권고를 생성하는 서비스로 간다.

---

## 2. 제품 정의

### 제품 한 줄 정의
**“산불 관련 위치를 입력하면, 공공/지형/기상/연료 데이터를 종합하고 에이전트가 오탐 가능성을 검토해 위험도와 대응 행동을 제안하는 웹 서비스”**

### 차별점
1. 기존 시스템의 확률값/경보값만 보여주는 방식 대신 설명 가능한 리포트를 제공
2. 안개/구름/가시성/습도/풍향 등 맥락을 함께 봐서 smoke/fire signal의 오탐 가능성을 교정
3. 일반인용 알림앱보다 공무원/진압대원/구조요원 시나리오에 맞춘 액션 추천 제공

### 핵심 사용자
- 공무원
- 진압대원
- 구조요원
- 데모용 보조 사용자: 시민

### 1차 사용자 플로우
1. 사용자가 지도 또는 좌표/주소로 위치 입력
2. 백엔드가 해당 위치 기준 상황 피처를 수집/정규화
3. 위험도 계산 모듈이 기본 wildfire risk score를 산출
4. LangGraph 에이전트가 오탐 가능성(안개/구름/저가시성/불일치 신호)을 검토
5. 에이전트가 대응 우선순위, 예상 위험요인, 권장 행동, 신뢰도/불확실성을 생성
6. 프론트엔드가 지도 + 위험 카드 + 근거 + 액션 체크리스트로 표시

---

## 3. 왜 이 방향이 맞는가

### 기존 AI 한계 근거(요약)
- `Novel Recursive BiFPN Combining with Swin Transformer for Wildland Fire Smoke Detection` (2022, DOI: `10.3390/f13122032`) 초록에서 기존 smoke detection network의 한계로 **low detection accuracy**와 **high false alarm rate**를 명시하고, cloud/fog 같은 interference object를 강조
- `YOLO-Based Models for Smoke and Wildfire Detection in Ground and Aerial Images` (2024, DOI: `10.3390/fire7040140`) 초록에서 smoke/fog/cloud, fire/lighting/sun glare 간 **visual similarity**가 큰 도전이라고 명시
- `A review of machine learning applications in wildfire science and management` (2020, DOI: `10.1139/er-2020-0019`)는 wildfire ML 전반의 한계로 **generalizability**, **interpretability**, **domain expertise necessity**를 지적

### 본 프로젝트의 전략적 포지셔닝
따라서 이 프로젝트는 “새 detection backbone 하나 더 제안”보다 아래 포지셔닝이 더 강함:
- **기존 탐지/예측 모델의 한계를 에이전트 루프가 후처리로 보완**
- 단일 점수 출력이 아니라 **근거 기반 의사결정 자동화** 제공
- 공공데이터 + reasoning dataset + LLM/LangGraph 결합이라는 스토리가 명확함

---

## 4. 권장 아키텍처

## 4.1 시스템 구성

### Frontend
- Next.js App Router
- TypeScript
- Tailwind CSS
- shadcn/ui
- MapLibre GL JS
- React Query

역할:
- 위치 입력
- 지도 시각화
- 위험 리포트 렌더링
- 시나리오 비교(선택)

### Backend
- FastAPI
- Pydantic
- Pandas / NumPy
- scikit-learn
- LangGraph
- Uvicorn

역할:
- 원천데이터/라벨데이터 ingestion
- 피처 정규화
- 규칙+모델 결합 위험도 계산
- 에이전트 루프 실행
- API 제공

### Storage
- 초기: SQLite
- 확장: Postgres + PostGIS
- 파일 저장: `backend/data/processed/` 내 parquet/json cache

### Deployment
- Frontend: Vercel
- Backend: Railway 또는 Render
- 향후 확장: Docker Compose, Fly.io, ECS

## 4.2 에이전트 그래프 (LangGraph)

```text
normalize_input
  -> retrieve_context
  -> score_risk
  -> review_false_positive
  -> recommend_actions
  -> generate_report
```

### 각 노드 역할
- `normalize_input`: 주소/좌표/행정구역 입력을 통일
- `retrieve_context`: 기상, 지형, 연료, 사회기반 정보 조회/매핑
- `score_risk`: 규칙 기반 + ML 보조 기반 위험도 계산
- `review_false_positive`: 안개, 구름, 낮은 가시성, 약풍, 습도 등 오탐 가능성 검토
- `recommend_actions`: 사용자 유형별 행동 권고 생성
- `generate_report`: UI 렌더링용 JSON 리포트 생성

## 4.3 MVP에서 모델링 전략
MVP는 복잡한 end-to-end 대규모 학습보다 아래 방식이 가장 현실적이다.

1. **Rule-based baseline**
   - 기상/건조/풍속/경사/취약계층/접근성을 이용한 점수화
2. **Dataset-derived calibration**
   - AI Hub 라벨의 reasoning/목적/질의를 사용해 설명 템플릿과 우선순위 로직 구성
3. **LLM agent layer**
   - 상충 신호 해석
   - 오탐 검토
   - 사용자 맞춤 리포트 생성

즉, 초기 MVP는 “LLM이 숫자를 직접 예측”하는 구조보다 **구조화된 점수 + 에이전트 해석**이 더 안전하고 설득력 있다.

---

## 5. 권장 저장소 구조

```text
project/
  frontend/
    app/
    components/
    features/
    lib/
    public/
    styles/
    package.json
  backend/
    app/
      api/
      agents/
      services/
      models/
      schemas/
      core/
      db/
      main.py
    data/
      raw/
      processed/
      fixtures/
    tests/
    requirements.txt
    pyproject.toml
  docs/
    architecture.md
    data-dictionary.md
    api-contract.md
    contest-story.md
  scripts/
    ingest_aihub.py
    build_feature_store.py
    seed_demo_data.py
  docker-compose.yml
  README.md
```

---

## 6. 화면 설계(MVP)

### 페이지 1: 메인 분석 페이지
블록:
- 위치 입력창(주소/좌표)
- 지도
- 위험도 요약 카드 (낮음/보통/높음/심각)
- 주요 근거 5개
- 오탐 검토 패널
- 권장 행동 패널
- 신뢰도/불확실성 배지

### 페이지 2: 시나리오 비교 페이지(선택)
- 현재 조건 vs 가정 조건(풍속 증가, 습도 감소 등)
- 대응 우선순위 변화 표시

### 페이지 3: 데이터/방법 소개 페이지
- 어떤 데이터로 판단했는지
- 에이전트 루프 설명
- 왜 일반 detection보다 나은지

---

## 7. 구현 순서

### Task 1: 프로젝트 기본 골격 생성

**Objective:** 빈 workspace에 프론트엔드/백엔드/문서 기본 구조를 만든다.

**Files:**
- Create: `frontend/`
- Create: `backend/`
- Create: `docs/`
- Create: `scripts/`
- Create: `README.md`
- Create: `docker-compose.yml`

**Step 1: Create frontend scaffold**
- `frontend/`에 Next.js + TypeScript 앱 생성

**Step 2: Create backend scaffold**
- `backend/app/main.py`, `backend/app/api`, `backend/app/agents`, `backend/app/services`, `backend/app/schemas` 생성

**Step 3: Create docs skeleton**
- `docs/architecture.md`
- `docs/data-dictionary.md`
- `docs/api-contract.md`

**Step 4: Verify structure**
Run:
```bash
find frontend backend docs scripts -maxdepth 2 | head -100
```
Expected:
- 주요 디렉터리들이 생성되어 있어야 함

---

### Task 2: 데이터 인벤토리 및 정규화 스크립트 작성

**Objective:** AI Hub 샘플 데이터를 서비스 입력으로 재사용할 수 있도록 정규화한다.

**Files:**
- Create: `scripts/ingest_aihub.py`
- Create: `backend/data/processed/incidents.json`
- Create: `docs/data-dictionary.md`

**Step 1: Write parser for source JSON**
- `fire_info`, `weather_conditions`, `terrain_conditions`, `fuel_conditions`, `Infra_Social`, `occurrence_status` 추출

**Step 2: Write parser for label JSON**
- `query`, `query_purpose`, `query_subject`, `query_type`, `confidence`, `reasoning_summary` 추출

**Step 3: Build normalized incident schema**
예시 필드:
```json
{
  "incident_id": "AS20240324",
  "region": "경기도",
  "lat": 37.110673,
  "lon": 127.297152,
  "user_type": "공무원",
  "risk_features": {
    "temperature": 18.4,
    "humidity_percent": 25.0,
    "wind_speed": 0.8,
    "slope": 6.74,
    "fuel_moisture": 15.0,
    "population": 1785.0
  },
  "label_metadata": {
    "query_purpose": "현황파악",
    "query_subject": "대피전략",
    "query_type": "composite"
  }
}
```

**Step 4: Verify output**
Run:
```bash
python3 scripts/ingest_aihub.py
```
Expected:
- `backend/data/processed/incidents.json` 생성
- 최소 1개 이상 incident가 저장됨

---

### Task 3: 위험도 산정 baseline 구현

**Objective:** 모델 학습 전에도 작동하는 baseline wildfire risk scoring을 만든다.

**Files:**
- Create: `backend/app/services/risk_engine.py`
- Create: `backend/tests/test_risk_engine.py`

**Step 1: Write failing test**
```python
def test_high_risk_when_low_humidity_high_wind_and_drought():
    features = {
        "humidity_percent": 18,
        "wind_speed": 8.5,
        "drought_duration_days": 28,
        "slope": 18,
        "fuel_moisture": 10,
        "population": 2000,
    }
    result = score_risk(features)
    assert result["risk_level"] in {"high", "critical"}
```

**Step 2: Run test to verify failure**
Run:
```bash
pytest backend/tests/test_risk_engine.py -v
```
Expected:
- FAIL

**Step 3: Write minimal implementation**
- humidity, wind, drought, slope, fuel_moisture, vulnerable/population, fire_station_distance를 가중합한 baseline 구현

**Step 4: Run test to verify pass**
Run:
```bash
pytest backend/tests/test_risk_engine.py -v
```
Expected:
- PASS

---

### Task 4: 오탐 검토 모듈 구현

**Objective:** 연기/산불 신호가 실제 위협인지, 안개/구름/저가시성 등 오탐 가능성이 큰지 설명하는 모듈을 만든다.

**Files:**
- Create: `backend/app/services/false_positive_review.py`
- Create: `backend/tests/test_false_positive_review.py`

**Step 1: Write failing test**
```python
def test_flags_false_positive_when_visibility_low_and_wind_weak():
    features = {
        "visibility": 400,
        "humidity_percent": 92,
        "wind_speed": 0.4,
        "surface_temperature": 8.0,
        "fire_intensity": "약함"
    }
    result = review_false_positive(features)
    assert result["false_positive_risk"] in {"medium", "high"}
```

**Step 2: Implement heuristics**
- 낮은 가시성
- 높은 습도
- 미약한 풍속
- 낮은 표면 온도
- 화재 강도 신호 약함

**Step 3: Verify**
Run:
```bash
pytest backend/tests/test_false_positive_review.py -v
```
Expected:
- PASS

---

### Task 5: LangGraph 에이전트 파이프라인 구현

**Objective:** baseline score와 false-positive review를 묶어 최종 판단 리포트를 생성한다.

**Files:**
- Create: `backend/app/agents/wildfire_graph.py`
- Create: `backend/app/schemas/report.py`
- Create: `backend/tests/test_wildfire_graph.py`

**Step 1: Define report schema**
필드 예시:
- `risk_level`
- `risk_score`
- `key_factors`
- `false_positive_risk`
- `recommended_actions`
- `confidence`
- `uncertainty_notes`

**Step 2: Wire LangGraph nodes**
- `normalize_input`
- `retrieve_context`
- `score_risk`
- `review_false_positive`
- `recommend_actions`
- `generate_report`

**Step 3: Verify graph**
Run:
```bash
pytest backend/tests/test_wildfire_graph.py -v
```
Expected:
- PASS

---

### Task 6: API 계약 구현

**Objective:** 프론트엔드가 바로 연결할 수 있는 분석 API를 제공한다.

**Files:**
- Create: `backend/app/api/routes/analyze.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_analyze_api.py`
- Modify: `docs/api-contract.md`

**Step 1: Define request/response**
Request:
```json
{
  "lat": 37.110673,
  "lon": 127.297152,
  "user_type": "공무원"
}
```

Response:
```json
{
  "risk_level": "high",
  "risk_score": 0.78,
  "key_factors": ["낮은 습도", "장기 가뭄", "취약계층 밀집"],
  "false_positive_risk": "medium",
  "recommended_actions": ["대피 우선구역 점검", "진입로 확보"],
  "confidence": 0.81
}
```

**Step 2: Verify API**
Run:
```bash
pytest backend/tests/test_analyze_api.py -v
```
Expected:
- PASS

---

### Task 7: 프론트엔드 분석 UI 구현

**Objective:** 심사위원이 바로 이해할 수 있는 데모 웹 화면을 만든다.

**Files:**
- Create: `frontend/app/page.tsx`
- Create: `frontend/components/map-panel.tsx`
- Create: `frontend/components/risk-summary-card.tsx`
- Create: `frontend/components/false-positive-panel.tsx`
- Create: `frontend/components/action-guide.tsx`
- Create: `frontend/lib/api.ts`

**Step 1: Build input form**
- 주소/좌표 입력
- 사용자 유형 선택

**Step 2: Build result layout**
- 위험도 카드
- 주요 근거
- 오탐 검토 패널
- 행동 가이드

**Step 3: Wire backend API**
- submit → `/api/analyze` or backend direct endpoint

**Step 4: Verify frontend**
Run:
```bash
npm run dev
```
Expected:
- 입력 후 분석 결과가 화면에 표시됨

---

### Task 8: 데모 데이터/시나리오 3종 구성

**Objective:** 심사/발표에서 재현 가능한 대표 상황을 만든다.

**Files:**
- Create: `backend/data/fixtures/demo_scenarios.json`
- Create: `docs/contest-story.md`

**Step 1: Prepare scenario A**
- 고위험/실제 대응 필요

**Step 2: Prepare scenario B**
- smoke-like signal but false-positive risk 높음

**Step 3: Prepare scenario C**
- 중위험/대응 우선순위 조정 필요

**Step 4: Verify scenario outputs**
- 각 시나리오별 결과가 명확히 달라야 함

---

### Task 9: 배포 구성

**Objective:** 실제 접속 가능한 웹사이트로 배포한다.

**Files:**
- Create: `frontend/.env.example`
- Create: `backend/.env.example`
- Create: `frontend/vercel.json` (필요 시)
- Create: `Dockerfile` 또는 `backend/Dockerfile`
- Modify: `README.md`

**Step 1: Environment variables 정리**
- API base URL
- LLM provider key
- data path / runtime mode

**Step 2: Deploy backend**
- Railway/Render/Fly.io 중 1개 선택

**Step 3: Deploy frontend**
- Vercel 배포

**Step 4: Verify production**
Run:
```bash
curl https://<backend-domain>/health
```
Expected:
- 200 OK

브라우저 확인:
- 프론트에서 분석 요청 성공

---

## 8. 파일 우선순위

### 먼저 만들 파일
- `backend/app/main.py`
- `backend/app/services/risk_engine.py`
- `backend/app/services/false_positive_review.py`
- `backend/app/agents/wildfire_graph.py`
- `frontend/app/page.tsx`
- `scripts/ingest_aihub.py`

### 바로 문서화할 파일
- `docs/architecture.md`
- `docs/data-dictionary.md`
- `docs/api-contract.md`
- `docs/contest-story.md`

---

## 9. 검증 전략

### 기능 검증
- 위치 입력 시 결과 JSON 반환
- 위험도와 행동 가이드가 함께 반환
- false-positive review가 별도 필드로 표시

### 데이터 검증
- 샘플 JSON ingestion 성공
- 숫자형 피처 누락 처리
- query metadata가 정상 보존

### 발표/심사 검증
- “탐지”가 아니라 “오탐 교정 + 의사결정” 차별점이 10초 내 설명 가능해야 함
- 시나리오 3개가 명확히 구분되어야 함
- 지도 + 근거 + 행동 권고가 한 화면에서 보여야 함

---

## 10. 리스크와 트레이드오프

### 리스크 1: 너무 많은 실시간 외부 데이터 연동
- 해결: MVP는 로컬/샘플 데이터 기반으로 먼저 완성
- 이후 MCP/공공 API 연동 추가

### 리스크 2: LLM이 정량 예측을 과장
- 해결: baseline score는 규칙/모델이 계산하고 LLM은 해석과 추천 중심으로 제한

### 리스크 3: 24시간 모니터링 요구로 과대확장
- 해결: 위치 입력형 분석 서비스로 범위를 제한

### 리스크 4: 탐지모델 자체 학습까지 하려다 일정 초과
- 해결: detection 모델 재학습은 옵션, 핵심 평가는 agentic decision-support로 가져감

---

## 11. 최종 추천

### 언어 선택
- **Frontend:** TypeScript
- **Backend/AI:** Python

### 구조 선택
- **Split-stack** 추천
  - `frontend/` = Next.js
  - `backend/` = FastAPI + LangGraph

### MVP 핵심 문장
**“위치 입력형 산불 의사결정 에이전트”**로 시작하고, “실시간 오탐 교정 루프”를 차별점으로 강조한다.

### 지금 바로 다음 액션
1. Next.js + FastAPI 기본 scaffold 생성
2. AI Hub 샘플 ingestion 스크립트 작성
3. 위험도 baseline + false-positive review 로직 구현
4. LangGraph 파이프라인 연결
5. 분석 결과 UI 및 배포
