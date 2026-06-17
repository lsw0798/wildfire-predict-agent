# Wildfire Agent Web Service Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 산림 데이터와 공공 실시간 데이터를 결합해 위치 입력 기반 산불 예측·감지·의사결정 자동화를 제공하는 배포 가능한 AI 에이전트 웹 서비스를 구축한다.

**Architecture:** 웹 프론트엔드에서 위치를 입력받고, 백엔드 API가 정적 산불 데이터셋 + 실시간 기상/공공 데이터 + 규칙/모델 기반 리스크 산출 + LangGraph 에이전트 루프를 결합해 결과를 생성한다. 첫 버전은 "실시간 24시간 모니터링" 대신 "사용자 위치 입력 → 에이전트 분석 → 예측/판단/행동 가이드 반환" 흐름에 집중한다.

**Tech Stack:** Next.js, TypeScript, FastAPI, Python, LangGraph, Pydantic, PostgreSQL(+PostGIS optional), Redis(optional), Vercel/Cloud Run/Render, Python data pipeline.

---

## Current Context

- 작업 경로: `/Users/leeseungwoo/Desktop/yoonity/4. 산림청 공모전/project`
- 자료 경로: `/Users/leeseungwoo/Desktop/yoonity/4. 산림청 공모전`
- 현재 `project/`는 사실상 비어 있음.
- 확인된 데이터 샘플:
  - `데이터/test/01. source/AS20240324_S_P0001_T001.json`
  - `데이터/test/02. label/AS20240324_T_P0001_T001.json`
- source JSON에는 다음 계층이 있음:
  - `raw_data_info.fire_info`
  - `source_data_info.user_info`
  - `source_data_info.weather_conditions`
  - `source_data_info.terrain_conditions`
  - `source_data_info.fuel_conditions`
  - `source_data_info.Infra_Social`
  - `source_data_info.occurrence_status`
- label JSON에는 LLM/에이전트형 응답 학습에 유용한 구조가 있음:
  - `query`
  - `tree_of_thought`
  - 위험 추론 branch / confidence / reasoning description
- 따라서 이 데이터는 단순 분류보다 **의사결정형 AI/에이전트 데모**에 매우 잘 맞음.

---

## Product Definition

### 핵심 사용자
- 산불 대응 관련 공무원/실무자
- 산림 관리 기관
- 재난 대응 의사결정 지원 담당자

### MVP 핵심 가치
1. 위치 입력만으로 산불 위험 및 대응 우선순위 제시
2. 기존 탐지 모델의 오탐 가능성(안개/구름/기상 혼동)을 에이전트가 재검토
3. 단순 점수 대신 실행 가능한 대응 가이드 제공

### MVP 사용자 플로우
1. 사용자가 지도/주소/좌표 입력
2. 시스템이 해당 위치의 지형/기상/연료/인프라/과거 산불 특성 조회
3. 기본 위험 점수 계산
4. LangGraph 에이전트가 데이터 검증 → 오탐 가능성 점검 → 대응 전략 생성
5. 웹에서 위험도, 근거, 추천 행동, 주의사항을 표시

---

## Recommended System Design

### 1. Frontend
- **추천:** Next.js 15 + TypeScript + Tailwind + Mapbox or Leaflet
- 이유:
  - 배포 빠름
  - 지도 UI 구현 편함
  - 공모전용 데모 품질 확보 쉬움
  - API와 연동 구조 명확

### 2. Backend
- **추천:** FastAPI
- 이유:
  - Python 데이터 처리 및 ML/LangGraph 연동 용이
  - JSON API 작성 빠름
  - 추후 모델 서빙/배치 작업 확장 쉬움

### 3. Agent Layer
- **추천:** LangGraph
- 노드 예시:
  - Input normalization node
  - Feature retrieval node
  - Risk scoring node
  - False-positive review node
  - Decision synthesis node
  - Report formatting node

### 4. Data Layer
- 초기 MVP:
  - 파일 기반 JSON/CSV 전처리 결과 + SQLite/Postgres
- 확장형:
  - PostgreSQL + PostGIS
  - 캐시용 Redis

### 5. Deployment
- 프론트: Vercel
- 백엔드: Render 또는 Google Cloud Run
- DB: Supabase Postgres 또는 Neon

---

## Architecture Proposal

### 입력
- 주소
- 위도/경도
- 선택적으로 관할 지역명

### 처리 파이프라인
1. 위치 정규화/지오코딩
2. 정적 산림/산불 feature 조회
3. 실시간 기상/공공 데이터 조회
4. 위험도 산출 모델 실행
5. 에이전트 검증 루프 실행
   - 데이터 일관성 검사
   - 오탐 가능성 검사
   - 대응 우선순위 추론
6. 결과 JSON 생성

### 출력
- 종합 위험도 (낮음/보통/높음/심각)
- 주요 근거 3~5개
- 오탐 가능성 판단
- 추천 대응 전략
- 주의사항
- 신뢰도/불확실성 표시

---

## Research Questions To Answer Early

1. 기존 산불 탐지/예측 AI의 대표적 한계는 무엇인가?
   - 안개/구름/연무 오탐
   - 지역 일반화 실패
   - 실시간 맥락 결합 부족
2. 공모전 심사에서 차별점은 무엇으로 보일 것인가?
   - 단순 예측이 아니라 **의사결정 자동화**
   - 에이전트 루프로 근거와 대안까지 제시
3. 실제 사용자에게 가장 중요한 한 화면은 무엇인가?
   - 지도 + 위험도 + 근거 + 즉시 행동 가이드

---

## Proposed Repository Structure

```text
project/
  frontend/
    app/
    components/
    lib/
    public/
    package.json
  backend/
    app/
      api/
      core/
      services/
      agents/
      models/
      schemas/
      db/
      main.py
    tests/
    requirements.txt
  data/
    raw/
    interim/
    processed/
  notebooks/
  docs/
    architecture.md
    data-dictionary.md
    api-spec.md
  scripts/
    ingest_aihub.py
    build_features.py
  .hermes/
    plans/
```

---

## Step-by-Step Plan

### Task 1: Create project scaffolding

**Objective:** 프론트엔드/백엔드/데이터/문서 구조를 먼저 확정한다.

**Files:**
- Create: `frontend/`
- Create: `backend/`
- Create: `data/`
- Create: `docs/`
- Create: `scripts/`

**Verification:**
- 각 디렉터리가 생성되어야 함
- 루트 구조가 팀원이 이해 가능한 수준으로 정리되어야 함

---

### Task 2: Build data inventory document

**Objective:** 현재 보유 데이터의 컬럼과 의미를 정리해 이후 모델/에이전트 설계 기준으로 사용한다.

**Files:**
- Create: `docs/data-dictionary.md`
- Read from: `../데이터/test/01. source/*.json`
- Read from: `../데이터/test/02. label/*.json`

**Must capture:**
- weather / terrain / fuel / infra / occurrence 변수 목록
- label JSON의 query / reasoning / confidence 구조
- 누락값/문자형 변수 목록

**Verification:**
- source/label 스키마와 대표 필드가 문서화되어 있어야 함

---

### Task 3: Define MVP API contract

**Objective:** 프론트와 백엔드가 병렬 개발 가능하도록 API를 먼저 확정한다.

**Files:**
- Create: `docs/api-spec.md`

**Endpoints:**
- `POST /analyze-location`
- `GET /health`
- `GET /reference/regions` (optional)

**Response shape draft:**
```json
{
  "risk_level": "high",
  "risk_score": 0.78,
  "false_positive_likelihood": 0.22,
  "key_factors": ["low humidity", "dense fuel", "high vulnerable population"],
  "recommended_actions": ["..."],
  "agent_reasoning_summary": "...",
  "confidence": 0.81
}
```

**Verification:**
- 프론트가 이 문서만 보고 mock UI를 만들 수 있어야 함

---

### Task 4: Implement backend skeleton

**Objective:** FastAPI 기본 서버와 분석 엔드포인트 틀을 만든다.

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/api/routes.py`
- Create: `backend/app/schemas/analyze.py`
- Create: `backend/requirements.txt`

**Core requirements:**
- health check
- analyze-location mock response
- Pydantic request/response schema

**Verification:**
- `uvicorn app.main:app --reload` 실행 가능
- `/health` 200 반환

---

### Task 5: Implement feature extraction pipeline

**Objective:** source JSON 데이터를 모델/룰 기반 분석 가능한 tabular feature로 변환한다.

**Files:**
- Create: `scripts/ingest_aihub.py`
- Create: `scripts/build_features.py`
- Create: `data/interim/`
- Create: `data/processed/`

**Feature groups:**
- weather
- terrain
- fuel
- infra/social
- occurrence

**Verification:**
- JSON 샘플 여러 개를 읽어 단일 표 형태 CSV/Parquet 생성 가능

---

### Task 6: Establish baseline risk scoring

**Objective:** 학습 모델 전이라도 동작하는 첫 위험도 계산기를 만든다.

**Files:**
- Create: `backend/app/services/risk_rules.py`
- Create: `backend/tests/test_risk_rules.py`

**Approach:**
- 낮은 습도, 높은 연료밀도, 긴 가뭄일수, 취약계층 밀도 등을 가중합
- 결과를 0~1 score + 4단계 라벨로 변환

**Verification:**
- 샘플 입력에 대해 일관된 score 출력
- 단위 테스트 통과

---

### Task 7: Add agent reasoning layer

**Objective:** 점수만 주는 것이 아니라 에이전트가 근거와 대응 전략을 생성하도록 한다.

**Files:**
- Create: `backend/app/agents/wildfire_graph.py`
- Create: `backend/app/agents/nodes.py`
- Create: `backend/app/services/decision_service.py`

**LangGraph node plan:**
- `collect_context`
- `score_risk`
- `review_false_positive`
- `generate_actions`
- `format_response`

**Verification:**
- mock 또는 실제 LLM 연결 시 structured response 생성
- 노드별 입력/출력 로그 확인 가능

---

### Task 8: Build false-positive correction logic

**Objective:** 본 서비스의 핵심 차별점인 오탐 교정 레이어를 설계한다.

**Files:**
- Create: `backend/app/services/false_positive_review.py`
- Create: `docs/false-positive-strategy.md`

**Checks to include:**
- 가시거리/습도/운량/강수와의 충돌 여부
- 열원/연기 추정과 지형·기상 맥락 불일치 여부
- 기존 탐지 결과와 공공 데이터 간 상충 여부

**Verification:**
- 위험도는 높지만 오탐 확률이 높은 케이스를 별도 표기 가능해야 함

---

### Task 9: Build MVP frontend

**Objective:** 공모전 데모에 충분한 UI를 만든다.

**Files:**
- Create: `frontend/app/page.tsx`
- Create: `frontend/components/map-panel.tsx`
- Create: `frontend/components/result-card.tsx`
- Create: `frontend/components/factor-list.tsx`
- Create: `frontend/lib/api.ts`

**UI sections:**
- 위치 입력/지도 선택
- 위험도 카드
- 근거 요약
- 대응 가이드
- 오탐 검토 결과

**Verification:**
- mock API 또는 실제 backend와 연결 가능
- 발표 시 1~2분 데모 가능 수준

---

### Task 10: Add deploy configuration

**Objective:** 실제 배포 가능한 형태를 만든다.

**Files:**
- Create: `frontend/.env.example`
- Create: `backend/.env.example`
- Create: `docs/deployment.md`
- Optional: `backend/Dockerfile`
- Optional: `frontend/vercel.json`

**Verification:**
- 프론트/백엔드 분리 배포 절차가 문서화되어 있어야 함

---

## Recommended Language / Framework Decision

### 최종 추천
- **Frontend:** TypeScript
- **Backend/AI/Data:** Python

### 왜 이렇게 나누는가
- 웹앱 UI/배포는 Next.js가 가장 빠름
- AI/데이터/에이전트는 Python 생태계가 압도적으로 유리
- LangGraph, pandas, FastAPI, 모델 서빙이 자연스럽게 연결됨

### 대안
- 올인원 Python(예: Streamlit): 개발 빠르지만 공모전용 “제품형 웹사이트” 완성도는 낮아질 수 있음
- 올인원 Node.js: 에이전트/데이터 파이프라인 생산성이 떨어질 수 있음

---

## What To Build First

### 1순위
- 데이터 사전
- 백엔드 mock API
- 프론트 mock 화면

### 2순위
- 위험도 baseline
- LangGraph 에이전트 루프

### 3순위
- 실시간 공공데이터 결합
- 배포

---

## Risks / Tradeoffs

1. **실시간 데이터 연동 범위가 커질수록 일정 리스크 증가**
   - MVP는 먼저 정적 데이터 + mock real-time 조합으로 시작
2. **오탐 교정의 정량 평가가 어려울 수 있음**
   - 규칙 기반 + 사례 기반 설명형 검증으로 초기 대응
3. **LLM hallucination 리스크**
   - 구조화된 입력/출력 + rule-based guardrail 필요
4. **24시간 감시형 제품으로 범위를 넓히면 과도함**
   - 지금은 “위치 입력형 의사결정 지원”에 집중

---

## Immediate Next Actions

1. `project/`에 기본 폴더 구조 생성
2. source/label JSON 20~50개 샘플 기준 데이터 사전 작성
3. FastAPI mock endpoint 생성
4. Next.js UI 초안 생성
5. 이후 LangGraph 에이전트 레이어 연결

---

## Recommendation For This Team Right Now

**이번 주 목표는 “동작하는 데모 뼈대”를 만드는 것**이 가장 좋다.

- 디자인보다 먼저 API 계약 확정
- 모델 고도화보다 먼저 위험도/근거/행동가이드가 나오는 end-to-end 흐름 완성
- 공모전에서는 “실제로 동작하는 제품 경험 + 차별적 스토리”가 중요함

이 프로젝트의 핵심 한 줄은 다음으로 정리 가능하다:

> **산불 탐지 정확도 문제를 단일 예측모델이 아니라, 공공데이터와 맥락 추론을 결합한 AI 에이전트 루프로 보완하는 의사결정 지원 웹 서비스**
