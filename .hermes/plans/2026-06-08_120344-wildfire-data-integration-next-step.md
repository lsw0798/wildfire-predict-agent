# Wildfire Data Integration Next-Step Implementation Plan

> **For Hermes:** Use subagent-driven-development style execution: implement backend/data/frontend in small verified steps.

**Goal:** 산불 위치도 shapefile, 경향성 CSV, 실시간 산불 API, Kakao 지도 키를 현재 웹 프로젝트에 연결해, `위치 입력 → 분석 요청 → 실제 데이터 기반 위험도/오탐/대응 가이드` 흐름을 만드는 것.

**Architecture:** 현재 구조는 유지한다. `frontend/`는 View, `backend/app/api/routes/`는 Controller, `backend/app/services/`는 데이터/도메인 로직, `backend/app/agents/`는 응답 orchestration을 담당한다. 데이터는 원천별로 바로 합치지 않고 `historical/fire map/realtime` 3개 레이어로 분리한 뒤 분석 시 조합한다.

**Tech Stack:** Next.js + TypeScript, FastAPI + Python, Kakao Maps JS SDK, CSV/XLSX 처리, shapefile 처리, 좌표계 변환, 외부 OpenAPI 연동.

---

## Current verified context

### Project
- Workspace: `/Users/leeseungwoo/Desktop/yoonity/4. 산림청 공모전/project`
- Frontend: Next.js + TypeScript
- Backend: FastAPI + services/agents/schemas 구조

### Verified assets
- Historical fire map shapefile:
  - `/Users/leeseungwoo/Desktop/yoonity/4. 산림청 공모전/데이터/산불발생위치도_전국/TB_FFAS_FF_OCCRR_ALL.shp`
- Historical trend CSV:
  - `/Users/leeseungwoo/Desktop/yoonity/4. 산림청 공모전/데이터/산불발생_경향성_분석용_데이터/WSQ000301.csv`
- Trend schema XLSX:
  - `/Users/leeseungwoo/Desktop/yoonity/4. 산림청 공모전/데이터/산불발생_경향성_분석용_데이터/WSQ000301_테이블정의서.xlsx`
- Wildfire API key RTF:
  - `/Users/leeseungwoo/Desktop/yoonity/4. 산림청 공모전/데이터/산불발생정보_API/산불발생정보API_KEY.rtf`
- Wildfire API usage PDF:
  - `/Users/leeseungwoo/Desktop/yoonity/4. 산림청 공모전/데이터/산불발생정보_API/산불발생정보_openapi_사용방법.pdf`
- Kakao JS key RTF:
  - `/Users/leeseungwoo/Desktop/yoonity/4. 산림청 공모전/데이터/카카오지도 API/kakao_DefaultJavascriptKey.rtf`

### Important facts from inspection
- Shapefile:
  - Point dataset
  - about 28,543 records
  - KGD2002 Unified Coordinate System
  - DBF/shape text handling and CRS conversion required
- Trend CSV:
  - 3,857 rows / 36 columns
  - 2014~2023
  - includes weather and occurrence factors
- Realtime wildfire API doc:
  - key validation endpoint exists
  - today fire endpoint exists
  - response appears mixed JSON/XML depending on endpoint
  - location detail may be limited, so treat realtime feed as status source first
- Current backend `/api/analyze` still uses hardcoded features
- Current frontend map area is placeholder only

---

## Proposed MVP behavior after this phase

1. 사용자가 지도에서 위치를 클릭하거나 위경도를 입력한다.
2. 프론트가 `POST /api/analyze`로 `lat/lon/user_type`를 보낸다.
3. 백엔드는:
   - 과거 경향성 CSV에서 지역/반경 기반 통계 조회
   - shapefile에서 인근 과거 발생 이력 조회
   - 실시간 산불 API에서 당일 상태 확인
   - 기존 risk/false-positive 엔진에 필요한 feature를 조합
4. 응답으로 위험도, 오탐 가능성, 주요 근거, 행동 가이드, 데이터 출처 요약을 돌려준다.
5. 프론트는 Kakao Map과 결과 카드로 이를 시각화한다.

---

## Files likely to change

### Backend
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/routes/analyze.py`
- Modify: `backend/app/agents/wildfire_graph.py`
- Modify: `backend/app/schemas/report.py`
- Modify: `backend/pyproject.toml`
- Create: `backend/app/core/config.py`
- Create: `backend/app/services/realtime_fire_api.py`
- Create: `backend/app/services/historical_fire_repository.py`
- Create: `backend/app/services/location_transform.py`
- Create: `backend/app/services/analysis_context_builder.py`
- Create: `backend/tests/test_historical_fire_repository.py`
- Create: `backend/tests/test_realtime_fire_api.py`
- Create: `backend/tests/test_analyze_route.py`

### Scripts / data prep
- Create: `scripts/ingest_wildfire_public_data.py`

### Frontend
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/components/map-panel.tsx`
- Modify: `frontend/app/globals.css`
- Modify: `frontend/lib/api.ts`
- Create: `frontend/components/analysis-dashboard.tsx`
- Create: `frontend/components/location-form.tsx`
- Create: `frontend/components/kakao-map.tsx`
- Create: `frontend/components/analysis-result-panel.tsx`
- Create: `frontend/lib/kakao-loader.ts`
- Create: `frontend/types/analysis.ts`

---

## Required env vars

### Backend
- `WILDFIRE_API_KEY`
- `WILDFIRE_API_BASE_URL`
- `WILDFIRE_API_TIMEOUT_SECONDS`
- `WILDFIRE_TREND_CSV_PATH`
- `WILDFIRE_TREND_SCHEMA_XLSX_PATH`
- `WILDFIRE_SHAPEFILE_PATH`
- `WILDFIRE_QUERY_RADIUS_KM`
- `WILDFIRE_ENABLE_REALTIME`
- `CORS_ALLOW_ORIGINS`

### Frontend
- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_KAKAO_JAVASCRIPT_KEY`
- optional: `NEXT_PUBLIC_DEFAULT_LAT`
- optional: `NEXT_PUBLIC_DEFAULT_LON`

---

## Step-by-step implementation order

### Phase 1: Secrets + config plumbing

#### Task 1: Add backend settings module
**Objective:** 환경변수와 데이터 경로를 코드에서 일관되게 읽게 만든다.

**Files:**
- Create: `backend/app/core/config.py`
- Modify: `backend/app/main.py`

**Steps:**
1. `config.py`에 settings class 추가
2. API key / 경로 / timeout / radius / realtime on/off 필드 정의
3. `main.py`에서 settings import 가능 상태로 연결
4. 아직 실사용은 하지 말고 import만 검증

**Validation:**
- `python -c "from app.core.config import settings; print(bool(settings))"`

---

#### Task 2: Extract keys from RTF into env files manually
**Objective:** 키를 소스 코드가 아니라 env로 안전하게 옮긴다.

**Files:**
- Create locally (not committed): `backend/.env`
- Create locally (not committed): `frontend/.env.local`

**Steps:**
1. RTF에서 키 값을 추출
2. backend `.env`에 `WILDFIRE_API_KEY` 저장
3. frontend `.env.local`에 `NEXT_PUBLIC_KAKAO_JAVASCRIPT_KEY` 저장
4. `.gitignore`에 이미 env 제외가 안 되어 있으면 추가

**Validation:**
- 키를 출력하지 말고 길이/존재 여부만 확인

---

### Phase 2: Data ingestion and normalization

#### Task 3: Create wildfire public-data ingest script scaffold
**Objective:** CSV/shapefile/xlsx를 읽어 정규화용 구조를 만들 스크립트 뼈대를 만든다.

**Files:**
- Create: `scripts/ingest_wildfire_public_data.py`

**Steps:**
1. 입력 경로 argparse 또는 settings 기반으로 받기
2. CSV 로더 함수 분리
3. shapefile 로더 함수 분리
4. schema xlsx alias loader 함수 분리
5. stdout 또는 JSON preview를 출력하도록 만들기

**Validation:**
- 스크립트 실행 시 row counts / key columns preview 출력

---

#### Task 4: Implement trend CSV normalization
**Objective:** CSV를 내부 분석용 사건/피처 구조로 정리한다.

**Files:**
- Modify: `scripts/ingest_wildfire_public_data.py`

**Steps:**
1. 실제 CSV 헤더를 source of truth로 사용
2. xlsx는 설명/alias 보조 정보로만 사용
3. 날짜/시간/수치형 필드 파싱
4. 내부 normalized dict 생성
5. 결과 샘플 몇 건을 저장 또는 출력

**Validation:**
- 총 행 수, 연도 범위, 주요 컬럼 null 비율 출력

---

#### Task 5: Implement shapefile metadata loading and CRS conversion
**Objective:** shapefile 사건을 WGS84 기반 조회 가능 상태로 만든다.

**Files:**
- Create: `backend/app/services/location_transform.py`
- Modify: `scripts/ingest_wildfire_public_data.py`

**Steps:**
1. KGD2002 Unified -> WGS84 변환 유틸 작성
2. shapefile row의 `TM_X/TM_Y` 변환
3. 지역명/원인/피해면적 등 메타 보존
4. 샘플 좌표를 위경도로 출력

**Validation:**
- 변환 후 좌표가 한국 범위에 들어가는지 확인

---

#### Task 6: Produce processed artifact for backend reads
**Objective:** 런타임마다 무거운 원본을 다시 읽지 않도록 가공 산출물을 만든다.

**Files:**
- Modify: `scripts/ingest_wildfire_public_data.py`
- Create: `backend/data/processed/` outputs

**Steps:**
1. `historical_trend_processed.json` 또는 csv/parquet 유사 산출물 생성
2. `fire_map_processed.json` 또는 lightweight lookup 산출물 생성
3. 생성 파일 경로를 문서화

**Validation:**
- backend에서 바로 읽을 수 있는지 preview

---

### Phase 3: Backend repositories and analysis flow

#### Task 7: Add historical repository service
**Objective:** 가공된 과거 데이터 조회 API를 서비스로 분리한다.

**Files:**
- Create: `backend/app/services/historical_fire_repository.py`
- Create: `backend/tests/test_historical_fire_repository.py`

**Steps:**
1. processed trend/fire-map 데이터 로드
2. 반경/최근접/지역기반 조회 메서드 추가
3. 결과를 분석 친화적 dict로 반환
4. 최소 단위 테스트 추가

**Validation:**
- 특정 lat/lon 입력에 대해 nearby count, cause summary, recent trend 반환 확인

---

#### Task 8: Add realtime wildfire API client
**Objective:** 실시간 산불 API를 안전하게 호출하고 응답을 정규화한다.

**Files:**
- Create: `backend/app/services/realtime_fire_api.py`
- Create: `backend/tests/test_realtime_fire_api.py`

**Steps:**
1. key check endpoint helper 추가
2. today fire endpoint 호출 함수 추가
3. XML/JSON parsing 분기 처리
4. 에러/timeout/fallback 처리
5. 실제 키 없이도 mock 응답으로 테스트 가능하게 구성

**Validation:**
- mocked responses로 정상/빈응답/오류응답 테스트

---

#### Task 9: Build analysis context builder
**Objective:** 위치 입력을 실제 feature 묶음으로 바꾼다.

**Files:**
- Create: `backend/app/services/analysis_context_builder.py`

**Steps:**
1. lat/lon/user_type 입력 수신
2. historical repository에서 통계/근접 사건 조회
3. realtime API에서 상태 조회
4. 기존 `risk_engine`/`false_positive_review`가 이해하는 feature dict 구성
5. UI에 보여줄 provenance summary도 함께 생성

**Validation:**
- 같은 입력에 대해 deterministic structured output 생성 확인

---

#### Task 10: Replace hardcoded analyze flow
**Objective:** `/api/analyze`가 실제 데이터 기반으로 응답하게 바꾼다.

**Files:**
- Modify: `backend/app/api/routes/analyze.py`
- Modify: `backend/app/agents/wildfire_graph.py`
- Modify: `backend/app/schemas/report.py`
- Create: `backend/tests/test_analyze_route.py`

**Steps:**
1. `analyze.py`에서 하드코딩 feature 제거
2. context builder 호출
3. `wildfire_graph.py`에서 risk + false positive + provenance + actions 조합
4. response schema에 데이터 출처/요약 필드 추가
5. route test 추가

**Validation:**
- `/api/analyze` 호출 시 좌표별 응답 차이가 생기는지 확인

---

#### Task 11: Add CORS and startup loading
**Objective:** 프론트와 백엔드가 로컬에서 바로 붙게 만든다.

**Files:**
- Modify: `backend/app/main.py`

**Steps:**
1. CORS middleware 추가
2. allowed origins를 settings로 받기
3. startup/lazy loading 전략 결정

**Validation:**
- frontend origin에서 preflight/POST 허용 확인

---

### Phase 4: Frontend map and analysis UX

#### Task 12: Create client dashboard state container
**Objective:** 분석 흐름을 페이지에서 분리한다.

**Files:**
- Create: `frontend/components/analysis-dashboard.tsx`
- Modify: `frontend/app/page.tsx`

**Steps:**
1. selected lat/lon, user type, loading, error, report state 추가
2. page는 dashboard만 렌더하도록 정리

**Validation:**
- 브라우저에서 기본 렌더 확인

---

#### Task 13: Add location form
**Objective:** 지도 클릭 없이도 좌표와 사용자 유형을 입력할 수 있게 한다.

**Files:**
- Create: `frontend/components/location-form.tsx`

**Steps:**
1. 위도/경도 입력 필드 추가
2. 사용자 유형 선택 추가
3. 분석 버튼 추가
4. 간단한 범위 검증 추가

**Validation:**
- 잘못된 좌표 입력 시 클라이언트 에러 표시

---

#### Task 14: Add Kakao script loader and map component
**Objective:** 실제 지도 렌더링을 붙인다.

**Files:**
- Create: `frontend/lib/kakao-loader.ts`
- Create: `frontend/components/kakao-map.tsx`
- Modify: `frontend/components/map-panel.tsx`

**Steps:**
1. SDK script loader Promise 작성
2. `window.kakao` 준비 후 지도 렌더
3. 지도 클릭 시 좌표 반환
4. 선택 위치 마커 표시

**Validation:**
- 지도 표시, 클릭, 마커 이동 확인

---

#### Task 15: Connect frontend to backend analyze API
**Objective:** 입력-분석-결과 흐름을 완성한다.

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/components/analysis-dashboard.tsx`
- Create: `frontend/components/analysis-result-panel.tsx`

**Steps:**
1. API error handling 보강
2. submit 시 loading state 처리
3. 응답을 기존 result cards에 바인딩
4. 결과 없을 때/에러일 때 UI 분기 추가

**Validation:**
- 지도 클릭 → 분석 → 결과 카드 업데이트 전체 흐름 확인

---

#### Task 16: Polish layout and mobile responsiveness
**Objective:** 공모전 데모 수준의 가독성을 확보한다.

**Files:**
- Modify: `frontend/app/globals.css`

**Steps:**
1. 2-column desktop / 1-column mobile 반응형 정리
2. 지도 최소 높이 확보
3. 로딩/에러/empty state 스타일 정리

**Validation:**
- 좁은 폭/넓은 폭에서 레이아웃 확인

---

## Test / verification checklist

### Backend
- processed data generation succeeds
- historical repository tests pass
- realtime API parser tests pass
- `/api/analyze` route tests pass
- local `uvicorn app.main:app --reload --port 8000` succeeds
- sample POST to `/api/analyze` returns real-data-based response

### Frontend
- `npm run dev` succeeds
- Kakao map renders with env key
- map click updates lat/lon
- analyze request succeeds against backend
- result cards reflect API response

### End-to-end
- user selects point on map
- request sent to backend with coordinates
- backend returns risk + false-positive + actions + source summary
- frontend displays result without console errors

---

## Biggest risks / tradeoffs

1. **CRS mismatch**
   - shapefile is not WGS84, so bad conversion will poison nearby-search logic.

2. **Schema drift between xlsx and CSV**
   - use actual CSV headers as truth; xlsx is documentation only.

3. **Realtime API location limitations**
   - if the API lacks useful coordinates, realtime should remain a status/provenance source, not the only spatial source.

4. **Encoding issues**
   - DBF/RTF/PDF/Korean text may require explicit handling.

5. **Performance**
   - repeatedly reading raw shapefile/CSV in request path will be slow; use processed artifacts or cached loaders.

6. **Security**
   - wildfire API key must never be exposed client-side.

---

## Recommended execution grouping

### Group A — Data foundation
- Tasks 1~6

### Group B — Backend integration
- Tasks 7~11

### Group C — Frontend UX
- Tasks 12~16

---

## Suggested immediate next action

Implement **Group A first**. The project already has UI and API skeletons, but they are still fed by mock/hardcoded data. The fastest path to meaningful progress is:
1. settings/env wiring,
2. public-data ingest script,
3. CRS-safe processed artifacts.

Once that exists, backend and frontend changes become much more deterministic.