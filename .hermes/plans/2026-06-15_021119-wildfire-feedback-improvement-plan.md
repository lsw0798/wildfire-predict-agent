# Wildfire Feedback Improvement Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 피드백 5가지를 반영해 웹 서비스를 2페이지 구조로 재편하고, 반경 기반 분석·신뢰도 표준오차·일반인용 XAI·지도 레이어 확장까지 이어질 수 있는 구현 순서를 정의한다.

**Architecture:** 기존 split-stack 구조를 유지한다. Frontend는 Next.js App Router에서 `모니터링 페이지`와 `위치 분석 페이지`로 분리하고, Backend는 FastAPI + LangGraph 흐름 위에 `모니터링용 집계 서비스`, `공간 반경 서비스`, `설명/XAI 응답 스키마`, `신뢰도 오차 계산기`를 추가한다. 위험도 전면 지도는 별도 집계 API와 프론트 맵 오버레이로 단계적으로 붙인다.

**Tech Stack:** Next.js 15 + TypeScript, FastAPI, LangGraph, Python services, Kakao Maps SDK, 기존 historical/realtime services

---

## 0. 현재 상태 요약

### 확인된 현재 구현
- 단일 페이지만 존재: `frontend/app/page.tsx`
- 위치 클릭/수동 입력 후 `/api/analyze` 호출
- 현재 백엔드 historical 반경 검색은 이미 존재함:
  - `backend/app/services/group_b_context.py:46-52`
  - `radius_km=50.0`, `limit=20`
- 즉 **현재는 프론트가 점 입력만 받고, 백엔드는 내부적으로 반경 50km 조회**를 수행하는 구조다.
- `AnalyzeResponse`는 아직 최소 스키마만 제공:
  - `risk_level`, `risk_score`, `false_positive_risk`, `confidence`, `key_factors`, `recommended_actions`, `uncertainty_notes`, `selected_tools`, `selection_reason`, `selection_mode`
- 위험도 요약 UI는 현재 간단한 카드 1개 수준:
  - `frontend/components/risk-summary-card.tsx`
- 지도 전체 위험도 / 산 30개 모니터링 / 반경 시각화 / 표준오차 표시는 아직 없음.

### 핵심 제약 / 오픈 질문
1. **산불 빈도 가장 많은 산 30곳**을 만들려면 “산 이름” 기준 데이터가 필요하다.
   - 현재 확인한 경향성 CSV 샘플에는 산 이름 컬럼이 명확하지 않다.
   - 후보 전략:
     - A. 현재 데이터의 행정구역/지번 기반으로 대표 산 지점 데이터셋 추가 확보
     - B. shapefile 또는 별도 산/봉우리 POI 데이터와 spatial join
     - C. 초기 버전은 “산불 빈도 높은 30개 지점/권역”으로 먼저 구현 후, 산 이름 데이터 확보 시 치환
2. 지도 전체 위험도는 성능과 계산 비용 이슈가 있으므로 **grid aggregation + 저신뢰 셀만 agent review** 전략으로 단계화해야 한다.
3. 표준오차(±n%)는 통계적 정의를 먼저 고정해야 한다.
   - 권장: confidence를 point estimate로 두고, 주변 incident sample 수/추정 필드 수/데이터 소스 품질을 반영한 `confidence_margin` 계산.

---

## 1. 구현 우선순위

1. **반경 기준 현재 동작 명세화**
2. **응답 스키마 확장(XAI + confidence margin)**
3. **위치 분석 페이지 개선(기존 페이지 업그레이드)**
4. **페이지 분리 + 실시간 모니터링 페이지 추가**
5. **지도 전체 위험도 레이어 및 selective agent review**

이 순서를 따르는 이유:
- 4번과 5번은 2번, 3번에서 만든 API/응답 구조를 재사용한다.
- 반경 동작을 먼저 명세화해야 UI 문구/시각화/분석 로직이 어긋나지 않는다.
- XAI/신뢰도 개편은 두 페이지 모두에 재사용된다.

---

## 2. 단계별 구현 계획

### Phase 1. 반경 기준 분석 현재 상태 명세화 + API 입력 확장 설계

### Task 1: 현재 반경 동작을 명시적으로 문서화
**Objective:** “점 클릭”이 실제로는 어떤 반경을 조회하는지 코드/문서/API 기준을 일치시킨다.

**Files:**
- Modify: `backend/app/services/group_b_context.py`
- Modify: `project/docs/api-contract.md`
- Modify: `project/docs/architecture.md`
- Test: `backend/tests/test_group_b_context.py`

**Implementation notes:**
- 현재 `build_historical_context()` 내부의 `radius_km=50.0`를 상수화한다.
- 예: `DEFAULT_ANALYSIS_RADIUS_KM = 50.0`
- API 문서에 “현재 분석은 입력 좌표 기준 반경 50km historical 탐색”이라고 명시한다.
- 테스트에서 기본 반경이 50km로 사용되는지 검증한다.

**Verification:**
- `backend/tests/test_group_b_context.py`에 기본 반경 assertion 추가
- 문서에 반경 설명 반영

### Task 2: AnalyzeRequest에 반경 파라미터 설계 추가
**Objective:** 향후 반경을 사용자가 제어하거나 프론트에서 명시할 수 있게 한다.

**Files:**
- Modify: `backend/app/schemas/report.py`
- Modify: `frontend/lib/wildfire-analysis.ts`
- Modify: `backend/app/api/routes/analyze.py`
- Test: `backend/tests/test_analyze_route.py`

**Implementation notes:**
- `AnalyzeRequest`에 `radius_km: float | None = None` 추가
- 미입력 시 백엔드 기본값 사용
- 유효 범위 예시: `1 <= radius_km <= 100`
- 프론트는 일단 optional field로만 반영하고 기본값은 숨겨도 됨

**Verification:**
- route test에서 `radius_km` 포함/미포함 둘 다 통과

### Task 3: 반경 끝점 계산 유틸 설계
**Objective:** 지도에서 반경 원 표시 및 “끝과 끝 점” 계산의 기반을 만든다.

**Files:**
- Create: `backend/app/services/spatial_radius.py`
- Test: `backend/tests/test_spatial_radius.py`

**Implementation notes:**
- 함수 예시:
  - `build_radius_bounds(lat, lon, radius_km) -> dict`
  - `build_cardinal_points(lat, lon, radius_km) -> {north, south, east, west}`
- 반환값은 이후 프론트 지도 원 표시와 설명 문구에 사용

**Verification:**
- 위도/경도 기준 북/남/동/서 점이 계산되는지 테스트
- 반경 0보다 크면 bounds가 달라지는지 테스트

---

### Phase 2. 신뢰도 표준오차(±n%)와 일반인용 XAI 응답 확장

### Task 4: confidence margin 계산 서비스 추가
**Objective:** 기존 `confidence`에 더해 `confidence_margin` 또는 `confidence_interval`을 계산한다.

**Files:**
- Create: `backend/app/services/confidence_metrics.py`
- Modify: `backend/app/agents/wildfire_graph.py`
- Modify: `backend/app/schemas/report.py`
- Test: `backend/tests/test_confidence_metrics.py`

**Implementation notes:**
- 1차 버전 권장 출력:
  - `confidence: float`
  - `confidence_margin: float`  # 예: 0.08 → ±8%
- 계산 입력 후보:
  - nearby incident count
  - estimated_fields count
  - realtime source live/fallback 여부
  - historical source live/estimated 여부
- 간단한 초기 공식을 먼저 고정:
  - 표본 수 적을수록 margin 증가
  - 추정 필드 많을수록 margin 증가
  - fallback source면 margin 증가
- “엄밀한 확률통계 기반 표준오차”가 아니라면 문서에서 **operational confidence margin**이라고 설명

**Verification:**
- incident 수가 적고 estimated_fields가 많을수록 margin이 커지는 테스트
- 응답 schema에 `confidence_margin` 포함

### Task 5: AnalyzeResponse에 XAI 전용 필드 추가
**Objective:** 일반인용 설명을 구조화해서 프론트가 읽기 쉽게 만든다.

**Files:**
- Modify: `backend/app/schemas/report.py`
- Modify: `backend/app/agents/wildfire_graph.py`
- Test: `backend/tests/test_services.py`
- Test: `backend/tests/test_analyze_route.py`

**Recommended response additions:**
- `confidence_margin: float`
- `analysis_radius_km: float`
- `radius_points: { north, south, east, west }`
- `risk_summary_text: str`
- `false_positive_summary_text: str`
- `xai_reasons: list[str]`
- `reviewed_signals: list[str]`
- `data_quality_summary: str`

**Implementation notes:**
- `uncertainty_notes`는 유지하되, 사용자 친화적 요약 필드를 별도 추가
- `risk_summary_text`는 “왜 높음/낮음인지” 한 문단으로 생성
- `false_positive_summary_text`는 “안개/시야/센서 오해 가능성”을 쉬운 문장으로 설명

**Verification:**
- analyze route 응답에 신규 필드 포함
- 기존 필드와 충돌 없이 테스트 통과

### Task 6: LangGraph 리포트 조립부에서 설명 레이어 강화
**Objective:** agent trace를 사용자용 XAI 요약과 내부 trace로 분리한다.

**Files:**
- Modify: `backend/app/agents/wildfire_graph.py`
- Test: `backend/tests/test_services.py`

**Implementation notes:**
- 현재 `uncertainty_notes`에 trace가 많이 들어감
- 분리 방향:
  - 사용자용: `risk_summary_text`, `false_positive_summary_text`, `xai_reasons`
  - 내부용/디버그용: `workflow_trace`, `agent_trace` (필요 시 별도 debug 플래그에서만 노출)
- 일반 사용자 UI에는 지나치게 기술적인 trace를 직접 노출하지 않도록 정리

**Verification:**
- 응답이 읽기 쉬운 문장 중심으로 바뀌는지 확인

---

### Phase 3. 기존 페이지를 “위치 분석 페이지”로 승격

### Task 7: App Router 페이지를 `/analyze`로 이동
**Objective:** 현재 단일 홈 페이지를 위치 분석 전용 페이지로 재배치한다.

**Files:**
- Create: `frontend/app/analyze/page.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/layout.tsx`

**Implementation notes:**
- 현재 `frontend/app/page.tsx`의 본문을 `frontend/app/analyze/page.tsx`로 옮긴다.
- 새 홈(`/`)은 모니터링 페이지 또는 랜딩/탭 허브로 전환
- 상단 네비게이션 추가:
  - `실시간 모니터링`
  - `위치 분석`

**Verification:**
- `/`와 `/analyze` 두 경로가 모두 렌더링됨
- build 통과

### Task 8: 위치 분석 페이지에 반경 UI 추가
**Objective:** 점 기반 입력을 반경 기반 입력으로 명확히 바꾼다.

**Files:**
- Modify: `frontend/app/analyze/page.tsx`
- Modify: `frontend/components/map-panel.tsx`
- Modify: `frontend/lib/wildfire-analysis.ts`

**Implementation notes:**
- 입력 폼에 반경(km) selector 추가
  - 초기값 50km
  - 옵션 예시: 5, 10, 20, 50 km
- 지도에 원(circle) 또는 반경 안내 텍스트 추가
- 선택 좌표와 반경 끝점 요약 표시

**Verification:**
- 반경 변경 후 analyze payload에 `radius_km` 포함
- 지도 텍스트/원 표시 업데이트

### Task 9: 위험도 요약 카드를 XAI 중심으로 재설계
**Objective:** 일반인이 이해 가능한 요약 + 신뢰도 ±오차 + 오탐 설명을 한눈에 보여준다.

**Files:**
- Modify: `frontend/components/risk-summary-card.tsx`
- Modify: `frontend/components/false-positive-panel.tsx`
- Create: `frontend/components/xai-summary-card.tsx`
- Modify: `frontend/app/analyze/page.tsx`

**Implementation notes:**
- `RiskSummaryCard`에 추가 표시:
  - 위험점수
  - 신뢰도
  - `± n%`
  - 현재 반경
- 새 `XaiSummaryCard`는 아래를 담당:
  - 왜 이런 판정인지
  - 어떤 요소가 크게 작용했는지
  - 오탐 우려가 있는지
  - 사용자가 어떻게 해석해야 하는지

**Verification:**
- mock response 기반 렌더링 테스트 추가 고려
- `next build` 통과

---

### Phase 4. 모니터링 페이지(상위 30곳) 추가

### Task 10: “상위 30곳” 데이터 정의 고정
**Objective:** 산 이름 기반인지, 지점/권역 기반인지 먼저 명확히 정의한다.

**Files:**
- Modify: `project/docs/data-dictionary.md`
- Create: `project/docs/monitoring-page-data-spec.md`

**Implementation notes:**
- 먼저 아래 중 하나를 공식 결정:
  - `top_30_mountains`
  - `top_30_hotspots`
  - `top_30_regions`
- 만약 산 이름 필드가 현재 데이터에 없다면, 초기 릴리스 명칭은 **“산불 빈도 상위 30개 감시 지점”** 으로 잡는 것이 안전함

**Verification:**
- 데이터 소스와 표시 명칭이 문서상 일치

### Task 11: 모니터링 집계 서비스 추가
**Objective:** 상위 30개 감시 대상 목록을 계산하는 backend 서비스를 만든다.

**Files:**
- Create: `backend/app/services/monitoring_hotspots.py`
- Create: `backend/app/schemas/monitoring.py`
- Create: `backend/app/api/routes/monitoring.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_monitoring_hotspots.py`

**Implementation notes:**
- 출력 필드 예시:
  - `id`
  - `name`
  - `lat`
  - `lon`
  - `historical_incident_count`
  - `latest_status`
  - `risk_level`
  - `confidence`
  - `confidence_margin`
  - `needs_agent_review`
- 실시간 API는 모든 점에 대해 일괄 호출이 어려우면 캐시/샘플 전략 필요
- 첫 버전은 historical ranking + realtime status enrichment 순서 권장

**Verification:**
- 상위 30개가 count 내림차순으로 나오는지 테스트
- schema validation 테스트

### Task 12: 실시간 모니터링 페이지 UI 구현
**Objective:** 첫 페이지에서 상위 30개 감시 대상을 표/지도 카드 형태로 보여준다.

**Files:**
- Create: `frontend/app/page.tsx`
- Create: `frontend/components/monitoring-dashboard.tsx`
- Create: `frontend/components/monitoring-hotspot-card.tsx`
- Create: `frontend/lib/monitoring.ts`

**Implementation notes:**
- 홈(`/`)을 모니터링 페이지로 사용
- 기본 구성:
  - 상단 요약 카드 (고위험 수, 저신뢰 수 등)
  - 지도 패널 (30개 마커)
  - 리스트/테이블 (정렬 가능하면 더 좋음)
  - “저신뢰 → 에이전트 검토 필요” 배지

**Verification:**
- API fetch + 렌더링 정상
- `next build` 통과

---

### Phase 5. 지도 전체 위험도 + 저신뢰 지점 selective agent review

### Task 13: 위험도 grid aggregation API 추가
**Objective:** 지도 전체에 뿌릴 수 있는 저해상도 위험도 셀 데이터를 생성한다.

**Files:**
- Create: `backend/app/services/risk_grid.py`
- Create: `backend/app/schemas/risk_grid.py`
- Create: `backend/app/api/routes/risk_grid.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_risk_grid.py`

**Implementation notes:**
- 입력: bounding box, zoom-ish level, optional radius
- 출력: grid cell list
  - `cell_id`
  - `center_lat`, `center_lon`
  - `risk_score`
  - `confidence`
  - `confidence_margin`
  - `needs_agent_review`
- 초기 버전은 Kakao tiles에 정확히 맞출 필요 없음. 단순 bbox/grid 분할로 충분

**Verification:**
- bbox 입력 시 셀 목록 생성 테스트
- confidence 낮은 셀 판단 테스트

### Task 14: low-confidence 셀만 agent review 대상으로 태깅
**Objective:** 전체 셀에 LangGraph 전체 루프를 돌리지 않고, 저신뢰 셀만 agent review 대상으로 올린다.

**Files:**
- Modify: `backend/app/services/risk_grid.py`
- Modify: `backend/app/services/confidence_metrics.py`
- Optionally Create: `backend/app/services/agent_review_gate.py`
- Test: `backend/tests/test_risk_grid.py`

**Implementation notes:**
- 예시 규칙:
  - `confidence < 0.6` 또는 `confidence_margin > 0.15`면 `needs_agent_review=True`
- 2차 버전에서만 선택된 셀에 상세 analyze endpoint 호출 또는 batch review endpoint 추가

**Verification:**
- 낮은 신뢰도 셀만 태깅되는지 테스트

### Task 15: 모니터링 지도에 위험도 heat/overlay 추가
**Objective:** 전체 지도 위험도와 저신뢰 지점을 동시에 보여준다.

**Files:**
- Modify: `frontend/components/map-panel.tsx`
- Modify: `frontend/components/monitoring-dashboard.tsx`
- Create: `frontend/components/risk-grid-overlay.tsx`
- Modify: `frontend/lib/monitoring.ts`

**Implementation notes:**
- Kakao Maps에서 polygon/rectangle overlay 또는 커스텀 marker로 셀 표현
- 저신뢰 셀은 색상/테두리/배지로 구분
- 지도 성능이 떨어지면 zoom threshold 도입

**Verification:**
- overlay가 렌더링되는지
- build 통과

---

## 3. 파일별 영향 범위 요약

### Backend likely changes
- `backend/app/schemas/report.py`
- `backend/app/api/routes/analyze.py`
- `backend/app/agents/wildfire_graph.py`
- `backend/app/services/group_b_context.py`
- `backend/app/services/historical_wildfire.py`
- `backend/app/main.py`
- `backend/app/services/confidence_metrics.py` (new)
- `backend/app/services/spatial_radius.py` (new)
- `backend/app/services/monitoring_hotspots.py` (new)
- `backend/app/services/risk_grid.py` (new)
- `backend/app/schemas/monitoring.py` (new)
- `backend/app/schemas/risk_grid.py` (new)
- `backend/app/api/routes/monitoring.py` (new)
- `backend/app/api/routes/risk_grid.py` (new)

### Frontend likely changes
- `frontend/app/page.tsx`
- `frontend/app/analyze/page.tsx` (new)
- `frontend/app/layout.tsx`
- `frontend/components/map-panel.tsx`
- `frontend/components/risk-summary-card.tsx`
- `frontend/components/false-positive-panel.tsx`
- `frontend/components/xai-summary-card.tsx` (new)
- `frontend/components/monitoring-dashboard.tsx` (new)
- `frontend/components/monitoring-hotspot-card.tsx` (new)
- `frontend/components/risk-grid-overlay.tsx` (new)
- `frontend/lib/wildfire-analysis.ts`
- `frontend/lib/monitoring.ts` (new)

### Docs likely changes
- `docs/api-contract.md`
- `docs/architecture.md`
- `docs/data-dictionary.md`
- `docs/monitoring-page-data-spec.md` (new)

### Tests likely changes
- `backend/tests/test_group_b_context.py`
- `backend/tests/test_analyze_route.py`
- `backend/tests/test_services.py`
- `backend/tests/test_spatial_radius.py` (new)
- `backend/tests/test_confidence_metrics.py` (new)
- `backend/tests/test_monitoring_hotspots.py` (new)
- `backend/tests/test_risk_grid.py` (new)

---

## 4. 검증 계획

### Backend
- `cd backend && ./.venv/bin/pytest -q`
- 신규 테스트 추가 후 전체 100% 통과 확인
- `/health` 확인
- `/api/analyze` sample payload로:
  - `radius_km` 미포함
  - `radius_km=10`
  - `radius_km=50`
- `/api/monitoring/hotspots` 확인
- `/api/risk-grid?...` 확인

### Frontend
- `cd frontend && npm run build`
- `/` 모니터링 페이지 렌더링
- `/analyze` 위치 분석 페이지 렌더링
- 지도에서 좌표 선택 → 반경 표시 → analyze 호출
- 저신뢰 셀/핫스팟 뱃지 표시 확인

### Product checks
- 일반인도 위험도 요약을 이해할 수 있는지 문장 검토
- `±n%` 표기가 과도하게 기술적이지 않은지 문장 보완
- “점 입력”과 “반경 분석”이 혼동되지 않도록 UI 문구 점검

---

## 5. 리스크 / 트레이드오프

### 리스크 1: 산 이름 데이터 부재 가능성
- 가장 큰 리스크
- 해결책: 초기 명칭을 “상위 30 감시 지점”으로 두고, 별도 산 데이터 확보 후 확장

### 리스크 2: 지도 전체 위험도는 비용/성능 부담
- 모든 셀에 LangGraph 적용은 비효율적
- 해결책: base risk grid는 규칙/경량 계산, 저신뢰 셀만 agent review

### 리스크 3: confidence ±오차의 해석성
- 엄밀한 통계량처럼 보이지만 실제는 운영적 근사치일 수 있음
- 해결책: UI 문구를 “신뢰도 오차 범위” 또는 “판정 오차폭”으로 표현하고 설명 제공

### 리스크 4: trace 과다 노출
- 현재는 기술 trace가 사용자 노트에 섞일 수 있음
- 해결책: user-facing explanation과 debug trace를 분리

---

## 6. 권장 실행 순서 (실제 작업 착수용)

### Sprint A — 안전한 기반 정리
1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6

### Sprint B — 기존 위치 분석 UX 개선
7. Task 7
8. Task 8
9. Task 9

### Sprint C — 모니터링 페이지 추가
10. Task 10
11. Task 11
12. Task 12

### Sprint D — 지도 전체 위험도 확장
13. Task 13
14. Task 14
15. Task 15

---

## 7. 즉시 결정이 필요한 항목

1. **“산 30곳”이 실제로 산 이름 기준이어야 하는가?**
   - 데이터가 없으면 1차는 `감시 지점 30곳`으로 가는 것이 현실적
2. **반경 기본값을 유지할지 변경할지**
   - 현재 내부 기본값은 50km
   - 사용자 체감상 10~20km가 더 직관적일 수 있음
3. **표준오차 용어 표기 방식**
   - `표준오차` 그대로 갈지
   - `신뢰도 오차 범위(±n%)`로 UX 표현할지
4. **지도 전체 위험도는 제출 전 필수인지, 고도화 옵션인지**
   - 공모전 일정에 따라 Sprint D는 옵션화 가능

---

## 8. 추천 첫 구현 묶음

가장 먼저 바로 실행할 추천 묶음은 아래 3개다.

1. **반경 명세화 + request schema 확장**
2. **confidence margin + XAI 응답 확장**
3. **기존 페이지를 `/analyze`로 옮기고 UI 개선**

이 3개가 끝나면,
- 피드백 2, 3, 4번은 실질 반영되고,
- 피드백 1번의 절반(페이지 분리 기반)도 완성되며,
- 이후 30개 모니터링 페이지와 전체 위험도 레이어가 붙기 쉬워진다.

---

Plan complete and saved. Ready to execute using subagent-driven-development — I'll dispatch a fresh subagent per task with full context and verify each increment. Shall I proceed with **Sprint A부터 실제 구현**할까?