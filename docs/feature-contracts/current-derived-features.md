# 현재 Derived Feature 계약서

## 목적
현재 산불 분석 파이프라인에서 `historical_context`, `realtime_context`, `derived_features`가 어떤 입력과 우선순위로 구성되는지 고정 문서로 정리한다.  
이 문서는 이후 confidence breakdown, reroute, ML adapter, GNN 확장 시 **기준선 계약서**로 사용한다.

---

## 1. 전체 흐름

현재 feature 생성 흐름은 아래와 같다.

1. 사용자 입력 수신
   - `lat`
   - `lon`
   - `user_type`
   - `radius_km`

2. `historical_context` 생성
   - 소스: 과거 산불 CSV / preview fallback
   - 위치 반경 내 incident 검색

3. `realtime_context` 생성
   - 소스: realtime wildfire API / fallback

4. `derive_group_b_features()` 실행
   - historical + realtime을 합쳐 파생 feature 구성

5. `risk_engine.score_risk()`가 일부 feature만 읽어 위험도 계산

---

## 2. 관련 코드 위치

- `backend/app/services/group_b_context.py`
- `backend/app/services/historical_wildfire.py`
- `backend/app/services/realtime_wildfire.py`
- `backend/app/services/risk_engine.py`
- `backend/app/agents/wildfire_graph.py`

---

## 3. historical_context 계약

### 3-1. 생성 함수
- `build_historical_context(...)`

### 3-2. 입력
- `latitude`
- `longitude`
- `radius_km` (없으면 `DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM = 50.0`)
- `HistoricalWildfireService`

### 3-3. 기본 동작
1. preview bundle에서 trend CSV 경로 확인
2. 가능하면 CSV 전체 로드
3. `find_nearby_incidents()`로 반경 내 incident 추출
4. `summarize_historical_context()`로 요약 생성
5. 실패 시 preview rows 기반 `estimated` 또는 `fallback`

### 3-4. 대표 출력 필드
| 필드 | 의미 | 출처 |
|---|---|---|
| `incident_count` | 반경 내 incident 개수 | nearby incidents 요약 |
| `latest_year` | 가장 최근 incident 연도 | nearby incidents 요약 |
| `top_causes` | 주요 원인 상위 목록 | nearby incidents 요약 |
| `source` | `live` / `estimated` / `fallback` | CSV 접근 가능 여부 |
| `radius_km` | 실제 적용 반경 | 입력 또는 기본값 |
| `row_count` | trend CSV 총 row 수 | preview summary |
| `trend_csv_path` | 실제 CSV 경로 | preview bundle 또는 service |
| `nearby_incidents` | 반경 내 incident 원본 목록 | CSV 필터 결과 또는 preview rows |
| `reason` | fallback 사유 | historical data unavailable 등 |

### 3-5. 중요 해석
- 현재 historical은 단순 통계 참고가 아니라 **지역 기반 과거 맥락**의 핵심 소스다.
- CSV가 없으면 응답은 가능하지만, 위치 기반 historical 의미는 약해진다.

---

## 4. realtime_context 계약

### 4-1. 생성 함수
- `build_realtime_context(...)`

### 4-2. 입력
- `latitude`
- `longitude`
- `realtime_status_provider`

### 4-3. 기본 동작
1. provider 호출
2. payload의 첫 번째 item 선택
3. 아래 상태 필드를 정규화

### 4-4. 대표 출력 필드
| 필드 | 의미 | 출처 |
|---|---|---|
| `source` | `live` / `fallback` / 기타 | realtime payload |
| `available` | 실시간 소스 사용 가능 여부 | realtime payload |
| `reason` | fallback 사유 | realtime payload |
| `status.humidity_percent` | 습도 | `humidity_percent` 또는 `HMDT` |
| `status.wind_speed` | 풍속 | `wind_speed` 또는 `WDSP` |
| `status.visibility` | 가시성 | `visibility` |
| `status.surface_temperature` | 표면/기온 | `surface_temperature`, `temperature`, `TPRT` |
| `status.fire_intensity` | 화재 강도/상태 | `fire_intensity` 또는 `status` |
| `raw_items` | 원본 응답 목록 | realtime payload |

### 4-5. 중요 해석
- 현재 realtime은 feature 생성의 1순위 입력이다.
- 다만 현재 provider는 lat/lon을 받아도 실질적으로 위치 기반 정밀성을 강하게 활용하지 않을 수 있으므로, 향후 좌표 기반 기상/센서 API로 대체 여지가 있다.

---

## 5. derived_features 계약

### 5-1. 생성 함수
- `derive_group_b_features(...)`

### 5-2. 현재 생성되는 필드 목록
| 필드 | 타입 | 생성 방식 | 우선순위 |
|---|---|---|---|
| `lat` | float | 사용자 입력 | 직접 입력 |
| `lon` | float | 사용자 입력 | 직접 입력 |
| `drought_duration_days` | int | `latest_year` 기반 파생 | historical only |
| `vulnerable` | float | nearby incidents의 `HASLV` 최대값 | historical only |
| `humidity_percent` | float | 실시간/평균/default | realtime → historical avg → default |
| `wind_speed` | float | 실시간/평균/default | realtime → historical avg → default |
| `visibility` | float | 실시간/default | realtime → default |
| `surface_temperature` | float | 실시간/평균/default | realtime → historical avg → default |
| `fire_intensity` | str | 실시간 또는 추정 | realtime → estimated |
| `estimated_fields` | list[str] | 추정 사용 항목 목록 | 생성 과정 부가정보 |

---

## 6. 필드별 상세 계약

### 6-1. `drought_duration_days`
- 함수: `_derive_drought_duration_days(historical_context)`
- 입력: `historical_context.latest_year`
- 규칙:
  - `latest_year`를 정수 변환
  - 현재 연도 1월 1일과 `latest_year`의 1월 1일 차이를 일수로 계산
  - 실패 시 `0`
- 주의:
  - 엄밀한 기상학적 “가뭄일수”가 아님
  - 현재는 historical recency 기반의 대체 지표
- risk engine 사용 여부: **사용함**

### 6-2. `vulnerable`
- 함수: `_derive_vulnerable(nearby_incidents)`
- 입력: nearby incidents의 `HASLV`
- 규칙:
  - 수치형으로 변환 가능한 값만 사용
  - 최대값 반환
  - 없으면 `0.0`
- risk engine 사용 여부: **사용함**

### 6-3. `humidity_percent`
- 함수: `_prefer_live_or_estimate(...)`
- 우선순위:
  1. `realtime_context.status.humidity_percent`
  2. nearby incidents 평균 `HMDT`
  3. default `45.0`
- 추정 시 `estimated_fields`에 `humidity_percent` 추가
- risk engine 사용 여부: **사용함**

### 6-4. `wind_speed`
- 우선순위:
  1. `realtime_context.status.wind_speed`
  2. nearby incidents 평균 `WDSP`
  3. default `1.0`
- 추정 시 `estimated_fields`에 `wind_speed` 추가
- risk engine 사용 여부: **사용함**

### 6-5. `visibility`
- 우선순위:
  1. `realtime_context.status.visibility`
  2. default `5000.0`
- historical 평균 사용 없음
- 추정 시 `estimated_fields`에 `visibility` 추가
- risk engine 사용 여부: **직접 사용 안 함**
- downstream 용도:
  - false positive review / 설명 / 신뢰도 보조 확장 여지

### 6-6. `surface_temperature`
- 우선순위:
  1. `realtime_context.status.surface_temperature`
  2. nearby incidents 평균 `TPRT`
  3. default `24.0`
- 추정 시 `estimated_fields`에 `surface_temperature` 추가
- risk engine 사용 여부: **직접 사용 안 함**

### 6-7. `fire_intensity`
- 우선순위:
  1. `realtime_context.status.fire_intensity`
  2. `_estimate_fire_intensity(...)`
- 추정 규칙:
  - 최대 피해면적 `FRFR_DMG_AREA >= 1.0`
  - 또는 `humidity_percent < 30`
  - 또는 `wind_speed >= 5`
  - 이 중 하나라도 만족 시 `"높음"`
  - 피해면적 `>= 0.3`이면 `"보통"`
  - 아니면 `"추정"`
- 추정 시 `estimated_fields`에 `fire_intensity` 추가
- risk engine 사용 여부: **직접 사용 안 함**
- downstream 용도:
  - 오탐/설명/추가 경로 판단 확장 후보

### 6-8. `estimated_fields`
- 의미: 실시간 관측이나 직접값이 없어 추정/기본값으로 채운 필드 목록
- 현재 영향:
  - confidence 하향
  - confidence margin 확대
  - data quality penalty 증가
- risk engine 사용 여부: **직접 사용 안 함**
- workflow 영향: **매우 큼**

---

## 7. risk_engine 실제 사용 필드 계약

현재 `score_risk(features)`가 직접 읽는 값은 다음과 같다.

| 필드 | 현재 공급 상태 | 사용 여부 | 기본값 |
|---|---|---|---|
| `humidity_percent` | 공급됨 | 사용 | `50` |
| `wind_speed` | 공급됨 | 사용 | `1` |
| `drought_duration_days` | 공급됨 | 사용 | `0` |
| `slope` | 현재 파이프라인에서 안정적 공급 확인 못함 | 사용 | `0` |
| `fuel_moisture` | 현재 파이프라인에서 안정적 공급 확인 못함 | 사용 | `20` |
| `vulnerable` | 공급됨 | 사용 | `0` |

### 해석
- 현재 위험도 계산에 실질적으로 자주 영향을 주는 핵심 필드는:
  - `humidity_percent`
  - `wind_speed`
  - `drought_duration_days`
  - `vulnerable`
- `slope`, `fuel_moisture`는 risk engine 인터페이스에는 존재하지만 현재 공급이 약하다.

---

## 8. source priority 요약표

| feature | 1순위 | 2순위 | 3순위 |
|---|---|---|---|
| `humidity_percent` | realtime | historical avg `HMDT` | default 45.0 |
| `wind_speed` | realtime | historical avg `WDSP` | default 1.0 |
| `surface_temperature` | realtime | historical avg `TPRT` | default 24.0 |
| `visibility` | realtime | 없음 | default 5000.0 |
| `fire_intensity` | realtime | estimated rule | 없음 |
| `drought_duration_days` | historical latest year | 없음 | 0 |
| `vulnerable` | historical `HASLV` max | 없음 | 0.0 |

---

## 9. 현재 구조의 한계

1. `drought_duration_days`는 기상학적 가뭄 데이터가 아니라 recency proxy다.
2. `vulnerable`의 의미가 도메인적으로 명확히 정제되지 않았고, 현재는 `HASLV` 최대값을 그대로 사용한다.
3. `slope`, `fuel_moisture`는 risk engine 입력이지만 안정적 upstream 공급이 부족하다.
4. realtime source는 좌표 정밀성이 약할 수 있어, 향후 위치 기반 기상/센서 API로 보강 필요가 있다.
5. `surface_temperature`, `visibility`, `fire_intensity`는 현재 risk engine 직접 입력은 아니므로, 예측 모델 도입 전까지는 설명/보조 지표 역할이 크다.

---

## 10. 후속 작업에 주는 의미

이 계약서를 기준으로 다음 작업을 진행한다.

1. confidence breakdown 설계
   - `estimated_fields`, source 상태, incident coverage를 구조적으로 반영
2. low-confidence diagnosis
   - 어떤 필드가 추정되었는지와 historical/realtime 약점을 원인으로 사용
3. reroute 설계
   - historical-heavy / realtime-heavy / conservative path 분기
4. ML adapter 설계
   - 현재 derived feature를 baseline feature table의 seed로 사용

---

## 11. 한 줄 결론

현재 feature 파이프라인은 **실시간 우선 + 과거 이력 보강 + default fallback** 구조이며, 위험도 계산은 이 중 일부 핵심 필드만 직접 사용하고 나머지는 신뢰도/설명/확장용 보조 신호로 쓰이고 있다.
