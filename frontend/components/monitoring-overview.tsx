"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { buildAnalyzeHref } from "../lib/analyze-navigation";
import { ForestHeatmapMap } from "./forest-heatmap-map";
import { MonitoringFetchResult, MonitoringWatchpoint, fetchMonitoringSummary } from "../lib/monitoring";

const fallbackHighlights = [
  {
    label: "대시보드 상태",
    value: "대기 중",
    hint: "백엔드 엔드포인트가 준비되면 실제 감시 지점 집계로 대체됩니다.",
  },
  {
    label: "권장 시작점",
    value: "/analyze",
    hint: "좌표·반경 기반 개별 지점 분석으로 바로 진입할 수 있습니다.",
  },
  {
    label: "Sprint B 목표",
    value: "모니터링 + 분석 분리",
    hint: "운영 개요와 정밀 분석 플로우를 서로 다른 페이지로 분리했습니다.",
  },
];

const priorityLabelMap: Record<string, string> = {
  high: "집중 감시",
  medium: "관찰 필요",
  low: "기본 감시",
};

function formatDateLabel(value?: string) {
  if (!value) {
    return "업데이트 정보 없음";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function getResultTone(status: MonitoringFetchResult["status"]) {
  if (status === "ready") {
    return "ready";
  }
  if (status === "unavailable") {
    return "idle";
  }
  return "error";
}

function formatPriorityLabel(value: string) {
  return priorityLabelMap[value] ?? value;
}

function getSuggestedRadiusKm(watchpoint: MonitoringWatchpoint) {
  if (watchpoint.priority_label === "high") {
    return 10;
  }
  if (watchpoint.priority_label === "medium") {
    return 5;
  }
  return 3;
}

function buildAnalyzeWatchpointHref(watchpoint: MonitoringWatchpoint, autoRun = false) {
  return buildAnalyzeHref({
    province: watchpoint.province,
    city: watchpoint.city,
    lat: watchpoint.lat,
    lon: watchpoint.lon,
    radiusKm: getSuggestedRadiusKm(watchpoint),
    autoRun,
  });
}

function buildMonitoringNotes(watchpoints: MonitoringWatchpoint[]) {
  if (watchpoints.length === 0) {
    return [];
  }

  const highPriorityCount = watchpoints.filter((item) => item.priority_label === "high").length;
  const latestYear = Math.max(...watchpoints.map((item) => item.latest_year ?? 0));
  const dominantCause = watchpoints[0]?.top_cause;

  return [
    `상위 ${watchpoints.length}개 감시 지점 중 ${highPriorityCount}개가 집중 감시(high)로 분류되었습니다.`,
    latestYear > 0 ? `현재 보드에는 최신 ${latestYear}년까지의 산불 발생 이력이 반영되어 있습니다.` : "최신 연도 정보가 일부 누락될 수 있습니다.",
    dominantCause ? `최상위 감시 지점의 대표 원인은 ${dominantCause}입니다.` : "대표 발화 원인 정보가 아직 충분하지 않습니다.",
  ];
}

export function MonitoringOverview() {
  const [monitoringResult, setMonitoringResult] = useState<MonitoringFetchResult>({
    status: "unavailable",
    message: "모니터링 요약을 아직 요청하지 않았습니다.",
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();

    fetchMonitoringSummary(controller.signal)
      .then((result) => setMonitoringResult(result))
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, []);

  const watchpoints = useMemo(() => {
    if (monitoringResult.status !== "ready") {
      return [];
    }
    return monitoringResult.summary.watchpoints;
  }, [monitoringResult]);

  const topTenWatchpoints = watchpoints.slice(0, 10);
  const highPriorityCount = watchpoints.filter((item) => item.priority_label === "high").length;
  const monitoredProvinces = new Set(watchpoints.map((item) => item.province)).size;
  const monitoringNotes = buildMonitoringNotes(topTenWatchpoints);

  return (
    <main className="main">
      <section className="hero hero--split">
        <div>
          <div className="hero__nav">
            <span className="badge">Monitoring</span>
          </div>
          <h1>산불 운영 모니터링 개요</h1>
          <p>
            홈 화면은 실제 감시 지점 상위 10개를 보여주는 운영 보드입니다. 지역별 누적 이력, 대표 발화 원인,
            우선순위를 확인한 뒤 분석 화면에서 에서 특정 좌표를 정밀 검토할 수 있습니다.
          </p>
        </div>
        <div className="hero__actions">
          <Link className="button button--inline" href="/analyze">
            좌표 분석
          </Link>
        </div>
      </section>

      <section className="overview-grid">
        <div className="panel overview-grid__main">
          <div className="card panel-section">
            <div className="card__header">
              <div>
                <div className="badge">백엔드 연결 상태</div>
                <h3 className="card__title">모니터링 요약</h3>
              </div>
              <span className={`status-chip status-chip--${loading ? "loading" : getResultTone(monitoringResult.status)}`}>
                {loading ? "연결 중" : monitoringResult.status === "ready" ? "연결됨" : monitoringResult.status === "unavailable" ? "폴백 사용" : "오류"}
              </span>
            </div>
            <div className={`state-banner state-banner--${loading ? "loading" : getResultTone(monitoringResult.status)}`}>
              {loading
                ? "백엔드 모니터링 요약 엔드포인트를 확인하고 있습니다."
                : monitoringResult.status === "ready"
                  ? `모니터링 요약 수신 완료 · ${formatDateLabel(monitoringResult.summary.generated_at)}`
                  : monitoringResult.message}
            </div>
          </div>

          <div className="metric-grid overview-metrics">
            {monitoringResult.status === "ready" ? (
              <>
                <div className="metric-card overview-metrics__item">
                  <span className="metric-card__label">전체 이력 건수</span>
                  <strong className="metric-card__value">{monitoringResult.summary.total_records}</strong>
                  <span className="metric-card__hint">CSV 기반 누적 산불 발생 레코드</span>
                </div>
                <div className="metric-card overview-metrics__item">
                  <span className="metric-card__label">표시 감시 지점</span>
                  <strong className="metric-card__value">{watchpoints.length}</strong>
                  <span className="metric-card__hint">홈 화면에 표시한 상위 우선순위 지점 수</span>
                </div>
                <div className="metric-card overview-metrics__item">
                  <span className="metric-card__label">집중 감시 지점</span>
                  <strong className="metric-card__value">{highPriorityCount}</strong>
                  <span className="metric-card__hint">priority_label=high 기준</span>
                </div>
                <div className="metric-card overview-metrics__item">
                  <span className="metric-card__label">관할 시도 수</span>
                  <strong className="metric-card__value">{monitoredProvinces}</strong>
                  <span className="metric-card__hint">상위 감시 지점이 분포한 시도 수</span>
                </div>
              </>
            ) : (
              fallbackHighlights.map((item) => (
                <div key={item.label} className="metric-card overview-metrics__item">
                  <span className="metric-card__label">{item.label}</span>
                  <strong className="metric-card__value metric-card__value--small">{item.value}</strong>
                  <span className="metric-card__hint">{item.hint}</span>
                </div>
              ))
            )}
          </div>

          <ForestHeatmapMap />

          <div className="cards">
            <div className="card panel-section">
              <div className="card__header">
                <div>
                  <div className="badge">운영 메모</div>
                  <h3 className="card__title">상황 공유 노트</h3>
                </div>
              </div>
              {monitoringNotes.length > 0 ? (
                <ul className="list rich-list">
                  {monitoringNotes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              ) : (
                <div className="empty-list">현재 공유된 운영 메모가 없습니다.</div>
              )}
            </div>
          </div>
        </div>

        <aside className="panel overview-grid__side">
          <div className="card panel-section">
            <div className="badge">빠른 작업</div>
            <h3 className="card__title">권장 운영 흐름</h3>
            <ol className="list rich-list rich-list--ordered">
              <li>홈 화면에서 상위 감시 지점과 우선순위 점수를 먼저 확인합니다.</li>
              <li>특정 지점을 클릭/복사한 뒤 /analyze로 이동해 좌표와 반경을 정밀 분석합니다.</li>
              <li>XAI 설명, 오탐 메모, 권장 행동을 근거로 현장 대응 우선순위를 조정합니다.</li>
            </ol>
          </div>

          <div className="card panel-section">
            <div className="badge">데이터 해석 기준</div>
            <h3 className="card__title">우선순위 점수 읽는 법</h3>
            <p className="card__lead">
              현재 우선순위는 누적 발생 건수, 최근 발생 이력, 대표 발화 원인을 기준으로 1차 산정합니다.
              이후 위험도가 높거나 판정 신뢰도가 낮은 지점은 분석 에이전트가 과거 이력, 실시간 산불 정보, 오탐 가능성, 데이터 품질을 단계적으로 검토해 정밀 판단합니다.
            </p>
          </div>

          <div className="card panel-section">
            <div className="card__header">
              <div>
                <div className="badge">우선 점검 지역</div>
                <h3 className="card__title">관제 우선순위 Top 10</h3>
                <p className="card__lead">우선순위 점수와 최근 이력을 기준으로 먼저 확인해야 할 지역입니다. 클릭하면 좌표 분석이 자동 실행됩니다.</p>
              </div>
            </div>
            {topTenWatchpoints.length > 0 ? (
              <>
                <div className="inline-summary inline-summary--monitoring">
                  <span className="card__lead">집중 감시 {highPriorityCount}개 / 총 {watchpoints.length}개 지점</span>
                  <span className="badge">관할 시도 {monitoredProvinces}곳</span>
                </div>
                <div className="monitoring-list">
                  {topTenWatchpoints.map((watchpoint, index) => {
                    const analyzeHref = buildAnalyzeWatchpointHref(watchpoint, true);
                    const priorityTone =
                      watchpoint.priority_label === "high"
                        ? "error"
                        : watchpoint.priority_label === "medium"
                          ? "loading"
                          : "idle";

                    return (
                      <Link
                        key={watchpoint.id}
                        className="monitoring-list__item monitoring-list__item--stacked monitoring-list__item--link"
                        href={analyzeHref}
                      >
                        <div className="monitoring-list__body">
                          <div className="monitoring-list__titleRow">
                            <strong>
                              {index + 1}. {watchpoint.province} {watchpoint.city}
                            </strong>
                            <span className={`status-chip status-chip--${priorityTone}`}>{formatPriorityLabel(watchpoint.priority_label)}</span>
                          </div>
                          <div className="chipRow monitoring-list__chips">
                            <span className="badge">누적 {watchpoint.incident_count}건</span>
                            <span className="badge">최근 {watchpoint.latest_year ?? "-"}년</span>
                            <span className="badge">원인 {watchpoint.top_cause ?? "미상"}</span>
                          </div>
                          <span className="ghostLink monitoring-list__action">
                            분석 열기 · 권장 반경 {getSuggestedRadiusKm(watchpoint)}km
                          </span>
                        </div>
                        <div className="monitoring-list__meta monitoring-list__meta--stacked">
                          <small>우선순위 점수</small>
                          <span>{watchpoint.priority_score}</span>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              </>
            ) : (
              <div className="empty-list">
                <p>모니터링 엔드포인트가 아직 없거나 감시 지점 데이터를 제공하지 않았습니다.</p>
                <Link className="ghostLink" href="/analyze">
                  그래도 좌표 기반 분석으로 바로 이동할 수 있습니다.
                </Link>
              </div>
            )}
          </div>
        </aside>
      </section>
    </main>
  );
}
