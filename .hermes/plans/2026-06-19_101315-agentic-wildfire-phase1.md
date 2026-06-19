# Agentic Wildfire Phase 1 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 현재 규칙 기반 산불 분석 파이프라인에 `신뢰도 원인 진단 → 대체 데이터 경로 재검토 → 설명 가능한 결과 반환`의 최소 골격을 추가한다.

**Architecture:** 기존 FastAPI + LangGraph + 규칙 기반 분석 구조는 유지한다. 다만 `source selector → historical/realtime 조회 → feature 생성 → 경로 진단 → 필요 시 보강 조회 → 위험도 계산 → 검토/보정` 흐름으로 확장해, 낮은 품질/결측/비활성 소스 조건에서 대체 경로를 실제로 한 번 더 실행하게 만든다.

**Tech Stack:** Python, FastAPI, LangGraph, Pydantic, pytest

---

## 현재 컨텍스트 / 가정

- 현재 LLM은 `backend/app/services/group_e_selector.py`에서 historical / realtime 조회 소스 선택에만 사용된다.
- 현재 위험도 계산은 `backend/app/services/risk_engine.py`의 규칙 기반 스코어링이다.
- 현재 confidence는 `backend/app/services/confidence_metrics.py`의 휴리스틱 margin 계산이다.
- 현재 LangGraph 흐름은 `select_sources -> fetch_historical -> fetch_realtime -> derive_features -> primary_assessment -> verification_gate -> reviews -> decision_adjustment -> compose_report -> build_response` 이다.
- 이번 Phase 1 목표는 ML/GNN 도입이 아니라, **낮은 품질의 데이터 상황에서 소스 재검토와 경로 전환의 최소 골격**을 코드에 심는 것이다.

---

## 제안 접근

1. `confidence_metrics.py`에 **원인 분해형 진단 함수**를 추가한다.
2. `wildfire_graph.py`에 **경로 진단 노드**와 **대체 소스 검토 노드**를 추가한다.
3. 진단 결과가 일정 조건을 만족하면,
   - Group E가 건너뛴 historical 또는 realtime 소스를 **2차 검토용으로 추가 조회**하고,
   - feature를 재생성한 뒤,
   - 그 결과로 1차 위험도 평가를 수행한다.
4. 최종 응답에는 최소한 다음 정보가 텍스트 형태로 남아야 한다.
   - 왜 경로 전환이 일어났는지
   - 어떤 소스를 추가 조회했는지
   - 여전히 어떤 한계가 남는지
5. 프론트 타입은 필요 시 optional 필드만 확장하고, 우선은 기존 UI를 깨지 않는 방향으로 유지한다.

---

## 단계별 계획

### Task 1: confidence 진단 함수 추가

**Objective:** 단순 margin 계산 외에, 낮은 신뢰도의 원인을 기계적으로 분류하는 진단 함수를 추가한다.

**Files:**
- Modify: `backend/app/services/confidence_metrics.py`
- Test: `backend/tests/test_confidence_metrics.py`

**구현 내용:**
- 새 함수 예시:
  - `diagnose_confidence_path(...) -> dict[str, Any]`
- 입력:
  - `estimated_fields`
  - `historical_source`
  - `realtime_source`
  - `nearby_incident_count`
- 출력 예:
  - `route`: `stable` | `augment_historical` | `augment_realtime` | `augment_both`
  - `reasons`: `["realtime_source_not_live", "estimated_fields_ge_3"]`
  - `severity`: `low` | `medium` | `high`
  - `summary`: 사용자용 요약 텍스트

**검증:**
- live/live + estimated 없음 → `stable`
- realtime skipped + estimated 많음 → `augment_realtime`
- historical skipped + realtime fallback → `augment_historical`

---

### Task 2: LangGraph 상태에 진단/재라우팅 정보 추가

**Objective:** 그래프 상태 객체에 confidence 진단과 보강 조회 결과를 담을 수 있게 확장한다.

**Files:**
- Modify: `backend/app/agents/wildfire_graph.py`

**구현 내용:**
- `AnalysisGraphState`에 아래 필드 추가:
  - `confidence_diagnostics: dict[str, Any]`
  - `route_decision: str`
  - `secondary_fetch_applied: list[str]`

---

### Task 3: 경로 진단 노드 추가

**Objective:** feature 생성 후, 위험도 계산 전에 현재 데이터 품질로 분석 경로를 유지할지/보강할지 판단한다.

**Files:**
- Modify: `backend/app/agents/wildfire_graph.py`

**구현 내용:**
- 새 노드: `diagnose_path`
- 내부에서 `diagnose_confidence_path()` 호출
- `workflow_trace`와 `agent_trace`에 사유 기록
- conditional edge 추가:
  - `stable` → `primary_assessment`
  - `reroute` → `augment_sources`

---

### Task 4: 대체 소스 보강 노드 추가

**Objective:** confidence 진단 결과에 따라 건너뛴 소스를 한 번 더 조회해 feature를 보강한다.

**Files:**
- Modify: `backend/app/agents/wildfire_graph.py`
- Reference: `build_historical_context`, `build_realtime_context`

**구현 내용:**
- 새 노드: `augment_sources`
- 진단 결과가 `augment_historical`면:
  - 현재 historical이 `skipped` 또는 `fallback/estimated`인 경우 historical 재조회
- 진단 결과가 `augment_realtime`면:
  - realtime 재조회
- `augment_both`면 둘 다 재시도
- 재조회 후 `derive_group_b_features()`를 다시 호출해 `derived_features` 갱신
- `secondary_fetch_applied` 기록

**검증:**
- 초기 선택이 realtime only였지만 estimated 많으면 historical 보강 실행
- 초기 선택이 historical only였지만 realtime skipped면 realtime 보강 실행

---

### Task 5: 보고서/응답에 재라우팅 근거 반영

**Objective:** 최종 응답에 “왜 경로 전환이 일어났는지”와 “무엇을 보강했는지”를 남긴다.

**Files:**
- Modify: `backend/app/agents/wildfire_graph.py`
- Modify (optional): `backend/app/schemas/report.py`
- Modify (optional): `frontend/lib/wildfire-analysis.ts`

**구현 내용:**
- `data_quality_summary` 또는 `uncertainty_notes`에 아래 포함
  - confidence 진단 summary
  - reroute reasons
  - secondary fetch applied
- 필요 시 새 응답 필드 optional 추가:
  - `confidence_diagnostics`
  - `analysis_strategy`

---

### Task 6: 테스트 보강

**Objective:** 새 경로 진단/보강 흐름이 실제로 동작하는지 회귀 테스트를 추가한다.

**Files:**
- Modify: `backend/tests/test_confidence_metrics.py`
- Modify: `backend/tests/test_analyze_route.py`
- Optional: create `backend/tests/test_wildfire_graph_reroute.py`

**검증 시나리오:**
1. live/live + estimated 없음 → reroute 없음
2. realtime skipped + estimated 다수 → reroute 발생, realtime 재조회
3. historical skipped + realtime fallback → reroute 발생, historical 재조회
4. 최종 응답 `uncertainty_notes`에 reroute 흔적 남음

---

## 변경 가능성이 높은 파일

- `backend/app/services/confidence_metrics.py`
- `backend/app/agents/wildfire_graph.py`
- `backend/tests/test_confidence_metrics.py`
- `backend/tests/test_analyze_route.py`
- `backend/app/schemas/report.py` (optional)
- `frontend/lib/wildfire-analysis.ts` (optional)

---

## 테스트 / 검증 계획

백엔드 기준 우선 검증:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_confidence_metrics.py -v
pytest tests/test_analyze_route.py -v
pytest -q
```

가능하면 smoke test:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

그 다음 샘플 호출:

```bash
curl -X POST http://127.0.0.1:8001/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"lat":37.5665,"lon":126.9780,"user_type":"시민"}'
```

확인 포인트:
- 응답이 깨지지 않는가
- `uncertainty_notes`에 reroute trace가 남는가
- 기존 필드(`risk_level`, `confidence`, `confidence_margin`) 유지되는가

---

## 리스크 / 트레이드오프

1. **실시간 API 재조회 비용**
   - reroute 시 추가 호출이 생길 수 있다.
   - Phase 1에서는 최대 1회 보강 조회로 제한하는 것이 안전하다.

2. **선택 로직과 재라우팅 로직 충돌 가능성**
   - Group E가 건너뛴 소스를 later stage에서 다시 조회하므로, “초기 선택”과 “보강 조회”의 의미를 trace에 명확히 남겨야 한다.

3. **진짜 AI라고 부르기엔 아직 부족**
   - 이번 단계는 ML/GNN 도입 전 단계다.
   - 그러나 “낮은 품질 원인 분석 → 대체 경로 보강”의 최소 오케스트레이션은 실제로 구현된다.

---

## 이번 턴에서 실제 구현 범위

이번 즉시 진행 범위는 아래로 제한한다.

- confidence path diagnosis 함수 추가
- wildfire_graph에 path diagnosis / source augmentation 노드 추가
- 테스트 추가 및 통과 확인

ML/GNN, 센서 융합 모델, 위성 데이터, OOD 탐지 등은 후속 Phase 2~4로 미룬다.
