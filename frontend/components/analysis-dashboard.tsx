"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { ActionGuide } from "./action-guide";
import { AnalysisCoverageCard } from "./analysis-coverage-card";
import { FalsePositivePanel } from "./false-positive-panel";
import { MapPanel } from "./map-panel";
import { RiskSummaryCard } from "./risk-summary-card";
import { SelectionMetadataCard } from "./selection-metadata-card";
import { SupportingEvidenceCard } from "./supporting-evidence-card";
import { buildInitialAnalysisFormState } from "../lib/analyze-navigation";
import { AnalyzeResponse, fetchWildfireAnalysis } from "../lib/wildfire-analysis";

const userTypeOptions = ["공무원", "진압대원", "구조요원", "시민"];
const radiusOptions = [1, 3, 5, 10, 20];

type DashboardFormState = ReturnType<typeof buildInitialAnalysisFormState>;
type RunSource = "auto" | "manual" | null;
type AnalysisPhase = "idle" | "prefill" | "loading" | "success" | "error";

type AnalysisDashboardProps = {
  initialFormState?: DashboardFormState;
  initialAutoRunRequested?: boolean;
  initialAutoRunKey?: string | null;
};

type ExecuteAnalysisOptions = {
  source: Exclude<RunSource, null>;
  suppressAbortError?: boolean;
};

function AnalysisSkeletonCard({ title, description }: { title: string; description: string }) {
  return (
    <div className="card panel-section card--skeleton" data-testid="analysis-skeleton-card">
      <div className="card__header">
        <div className="skeletonStack">
          <span className="skeletonLine skeletonLine--badge" />
          <span className="skeletonLine skeletonLine--title" />
        </div>
        <span className="status-chip status-chip--loading">준비 중</span>
      </div>
      <p className="card__lead">{title}</p>
      <div className="state-banner state-banner--loading">{description}</div>
      <div className="skeletonStack">
        <span className="skeletonLine skeletonLine--full" />
        <span className="skeletonLine skeletonLine--medium" />
        <span className="skeletonLine skeletonLine--short" />
      </div>
    </div>
  );
}

function AnalysisLoadingState({ runSource }: { runSource: Exclude<RunSource, null> }) {
  return (
    <>
      <div className="card statusCard statusCard--loading">
        <div className="card__header">
          <div>
            <div className="badge">분석 결과 준비 중</div>
            <h3 className="card__title">결과 카드 생성 중</h3>
          </div>
          <span className="status-chip status-chip--loading">진행 중</span>
        </div>
        <p className="card__lead">
          {runSource === "auto"
            ? "모니터링 페이지에서 전달된 위치를 기준으로 위험도·오탐 가능성·설명 근거를 차례로 불러오고 있습니다."
            : "입력한 좌표 기준으로 위험도·오탐 가능성·설명 근거를 차례로 계산하고 있습니다."}
        </p>
      </div>
      <AnalysisSkeletonCard title="위험도 요약" description="위험도와 신뢰도를 계산하고 있습니다." />
      <AnalysisSkeletonCard title="조회 소스 판단 근거" description="이번 위치에 필요한 조회 소스와 판단 근거를 정리하고 있습니다." />
      <AnalysisSkeletonCard title="반경 및 데이터 품질" description="지도 반경과 데이터 품질 요약을 계산하고 있습니다." />
      <AnalysisSkeletonCard title="사용자용 판단 근거" description="위험도 상승 요인과 XAI 설명을 정리하고 있습니다." />
      <AnalysisSkeletonCard title="대응 체크리스트" description="위험도에 맞춘 대응 우선순위를 정리하고 있습니다." />
    </>
  );
}

export function AnalysisDashboard({
  initialFormState,
  initialAutoRunRequested = false,
  initialAutoRunKey = null,
}: AnalysisDashboardProps) {
  const [formState, setFormState] = useState<DashboardFormState>(
    initialFormState ?? buildInitialAnalysisFormState(new URLSearchParams()),
  );
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runSource, setRunSource] = useState<RunSource>(null);
  const [analysisPhase, setAnalysisPhase] = useState<AnalysisPhase>("idle");
  const inFlightControllerRef = useRef<AbortController | null>(null);
  const lastAutoRunKeyRef = useRef<string | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    if (!initialFormState) {
      return;
    }

    setFormState(initialFormState);
    setResult(null);
    setError(null);
    setAnalysisPhase("idle");
  }, [initialFormState]);

  useEffect(() => {
    return () => {
      inFlightControllerRef.current?.abort();
    };
  }, []);

  const selectedCoordinates =
    Number.isFinite(Number(formState.lat)) && Number.isFinite(Number(formState.lon))
      ? {
          lat: Number(formState.lat),
          lng: Number(formState.lon),
        }
      : null;

  const requestedRadiusKm = Number(formState.radiusKm);
  const displayedRadiusKm = result?.analysis_radius_km ?? (Number.isFinite(requestedRadiusKm) ? requestedRadiusKm : null);
  const showInitialSkeleton = loading && !result;
  const showRefreshingState = loading && Boolean(result);
  const showAutoRunLoadingBanner = runSource === "auto" && (analysisPhase === "prefill" || analysisPhase === "loading");
  const showManualLoadingBanner = runSource === "manual" && showInitialSkeleton;

  const handleCoordinateSelect = useCallback((coordinates: { lat: number; lng: number }) => {
    setFormState((current) => ({
      ...current,
      lat: coordinates.lat.toFixed(6),
      lon: coordinates.lng.toFixed(6),
    }));
  }, []);

  const executeAnalysis = useCallback(
    async (
      nextFormState: DashboardFormState,
      controller: AbortController,
      options: ExecuteAnalysisOptions,
    ) => {
      const lat = Number(nextFormState.lat);
      const lon = Number(nextFormState.lon);
      const radiusKm = Number(nextFormState.radiusKm);

      setRunSource(options.source);

      if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        setAnalysisPhase("error");
        setError("위도와 경도를 숫자로 입력해 주세요.");
        setResult(null);
        return;
      }

      if (!Number.isFinite(radiusKm) || radiusKm <= 0) {
        setAnalysisPhase("error");
        setError("반경은 0보다 큰 숫자로 입력해 주세요.");
        setResult(null);
        return;
      }

      const requestId = requestIdRef.current + 1;
      requestIdRef.current = requestId;
      inFlightControllerRef.current = controller;
      setLoading(true);
      setError(null);
      setAnalysisPhase("loading");

      try {
        const response = await fetchWildfireAnalysis(
          {
            lat,
            lon,
            user_type: nextFormState.userType,
            radius_km: radiusKm,
          },
          controller.signal,
        );

        if (requestId !== requestIdRef.current || controller.signal.aborted) {
          return;
        }

        setResult(response);
        setAnalysisPhase("success");
      } catch (caughtError) {
        const isAbortError = caughtError instanceof Error && caughtError.name === "AbortError";

        if (isAbortError && options.suppressAbortError) {
          return;
        }

        if (requestId !== requestIdRef.current || controller.signal.aborted) {
          return;
        }

        setResult(null);
        setAnalysisPhase("error");
        setError(caughtError instanceof Error ? caughtError.message : "알 수 없는 오류가 발생했습니다.");
      } finally {
        if (requestId === requestIdRef.current) {
          setLoading(false);
        }

        if (inFlightControllerRef.current === controller) {
          inFlightControllerRef.current = null;
        }
      }
    },
    [],
  );

  useEffect(() => {
    if (!initialFormState || !initialAutoRunRequested || !initialAutoRunKey) {
      return;
    }

    if (lastAutoRunKeyRef.current === initialAutoRunKey) {
      return;
    }

    lastAutoRunKeyRef.current = initialAutoRunKey;
    setRunSource("auto");
    setAnalysisPhase("prefill");
    inFlightControllerRef.current?.abort();
    const controller = new AbortController();

    void executeAnalysis(initialFormState, controller, { source: "auto", suppressAbortError: true });

    return () => {
      controller.abort();
    };
  }, [executeAnalysis, initialAutoRunKey, initialAutoRunRequested, initialFormState]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    inFlightControllerRef.current?.abort();
    const controller = new AbortController();
    await executeAnalysis(formState, controller, { source: "manual" });
  };

  return (
    <main className="main">
      <section className="hero hero--compact">
        <div className="hero__nav">
          <span className="badge">Sprint B / Analyze</span>
          <Link className="ghostLink" href="/">
            모니터링 개요로 이동
          </Link>
        </div>
        <h1>위치·반경 기반 산불 분석 워크플로</h1>
        <p>
          좌표와 반경을 함께 지정하면 위험도, 오탐 가능성, XAI 설명, 데이터 품질 요약까지 한 화면에서 확인할 수
          있습니다.
        </p>
        {formState.sourceLabel ? (
          <div className="state-banner state-banner--idle">
            모니터링 페이지에서 전달된 감시 지점: <strong>{formState.sourceLabel}</strong>
            {initialAutoRunRequested ? " · 진입 즉시 분석을 자동 실행합니다." : ""}
          </div>
        ) : null}
        {showAutoRunLoadingBanner ? (
          <div className="state-banner state-banner--loading state-banner--auto-run">
            모니터링 페이지에서 전달된 위치를 기준으로 자동 분석을 시작했습니다. 위험도·오탐 가능성·설명 근거를 차례로 불러오고 있습니다.
          </div>
        ) : null}
        {showManualLoadingBanner ? (
          <div className="state-banner state-banner--loading state-banner--auto-run">
            입력한 좌표 기준으로 분석을 시작했습니다. 반경 {formState.radiusKm}km 범위를 바탕으로 결과를 계산하고 있습니다.
          </div>
        ) : null}
      </section>

      <section className="grid">
        <div className="panel">
          <form className="form" onSubmit={handleSubmit}>
            <label className="label" htmlFor="lat">
              위도
            </label>
            <input
              className="input"
              id="lat"
              name="lat"
              onChange={(event) => setFormState((current) => ({ ...current, lat: event.target.value }))}
              value={formState.lat}
            />

            <label className="label" htmlFor="lon">
              경도
            </label>
            <input
              className="input"
              id="lon"
              name="lon"
              onChange={(event) => setFormState((current) => ({ ...current, lon: event.target.value }))}
              value={formState.lon}
            />

            <label className="label" htmlFor="radiusKm">
              분석 반경 (km)
            </label>
            <input
              className="input"
              id="radiusKm"
              inputMode="decimal"
              min="0.1"
              name="radiusKm"
              onChange={(event) => setFormState((current) => ({ ...current, radiusKm: event.target.value }))}
              step="0.1"
              value={formState.radiusKm}
            />
            <div className="chipRow" role="list" aria-label="반경 빠른 선택">
              {radiusOptions.map((option) => {
                const active = Number(formState.radiusKm) === option;
                return (
                  <button
                    key={option}
                    aria-pressed={active}
                    className={`chipButton${active ? " chipButton--active" : ""}`}
                    onClick={() => setFormState((current) => ({ ...current, radiusKm: option.toString() }))}
                    type="button"
                  >
                    {option}km
                  </button>
                );
              })}
            </div>

            <label className="label" htmlFor="userType">
              사용자 유형
            </label>
            <select
              className="select"
              id="userType"
              name="userType"
              onChange={(event) => setFormState((current) => ({ ...current, userType: event.target.value }))}
              value={formState.userType}
            >
              {userTypeOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>

            <button className="button" disabled={loading} type="submit">
              {loading ? "분석 중..." : "분석 실행"}
            </button>
          </form>

          <div className={`cards${showInitialSkeleton ? " cards--loading" : ""}${showRefreshingState ? " cards--refreshing" : ""}`}>
            <div className="card statusCard">
              <div className="card__header">
                <div>
                  <div className="badge">현재 선택</div>
                  <h3 className="card__title">분석 입력 요약</h3>
                </div>
                {loading ? (
                  <span className="status-chip status-chip--loading">{runSource === "auto" ? "자동 분석 준비 중" : "재분석 중"}</span>
                ) : displayedRadiusKm ? (
                  <span className="status-chip status-chip--idle">반경 {displayedRadiusKm}km</span>
                ) : null}
              </div>
              <p className="card__lead">선택 반경은 지도 원형 오버레이와 백엔드 분석 범위에 동시에 적용됩니다.</p>
              <div className="detailList">
                <div>
                  <span>위도</span>
                  <strong>{formState.lat}</strong>
                </div>
                <div>
                  <span>경도</span>
                  <strong>{formState.lon}</strong>
                </div>
                <div>
                  <span>사용자 유형</span>
                  <strong>{formState.userType}</strong>
                </div>
                <div>
                  <span>유입 경로</span>
                  <strong>{formState.sourceLabel ?? "직접 입력"}</strong>
                </div>
              </div>
            </div>

            {error ? <div className="card statusCard errorCard">오류: {error}</div> : null}

            {showRefreshingState ? (
              <div className="card statusCard statusCard--loading">
                입력값이 변경되어 분석 결과를 새로 계산하고 있습니다. 이전 결과는 유지됩니다.
              </div>
            ) : null}

            {showInitialSkeleton ? (
              <AnalysisLoadingState runSource={runSource ?? "manual"} />
            ) : result ? (
              <>
                <RiskSummaryCard
                  confidence={result.confidence}
                  confidenceMargin={result.confidence_margin}
                  isLoading={showRefreshingState}
                  riskLevel={result.risk_level}
                  riskScore={result.risk_score}
                  status={showRefreshingState ? "loading" : "ready"}
                  summaryText={result.risk_summary_text}
                />
                <SelectionMetadataCard
                  selectedTools={result.selected_tools}
                  selectionMode={result.selection_mode}
                  selectionReason={result.selection_reason}
                />
                <AnalysisCoverageCard
                  confidenceMargin={result.confidence_margin}
                  dataQualitySummary={result.data_quality_summary}
                  radiusKm={result.analysis_radius_km}
                  radiusPoints={result.radius_points}
                />
                <SupportingEvidenceCard
                  keyFactors={result.key_factors}
                  reviewedSignals={result.reviewed_signals}
                  xaiReasons={result.xai_reasons}
                />
                <FalsePositivePanel
                  isLoading={showRefreshingState}
                  level={result.false_positive_risk}
                  notes={result.uncertainty_notes}
                  status={showRefreshingState ? "loading" : "ready"}
                  summaryText={result.false_positive_summary_text}
                />
                <ActionGuide actions={result.recommended_actions} isLoading={showRefreshingState} status={showRefreshingState ? "loading" : "ready"} />
              </>
            ) : !loading ? (
              <div className="card statusCard">좌표·반경·사용자 유형을 입력한 뒤 분석을 실행하면 결과가 여기에 표시됩니다.</div>
            ) : null}
          </div>
        </div>
        <div className="panel">
          <MapPanel
            analysisRadiusKm={displayedRadiusKm}
            radiusPoints={result?.radius_points}
            selectedCoordinates={selectedCoordinates}
            onCoordinateSelect={handleCoordinateSelect}
          />
        </div>
      </section>
    </main>
  );
}
