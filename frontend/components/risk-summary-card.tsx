type Props = {
  riskLevel: string;
  riskScore: number;
  confidence: number;
  confidenceMargin?: number;
  summaryText?: string;
  status?: "idle" | "loading" | "ready" | "error";
  isLoading?: boolean;
  error?: string | null;
};

const riskToneMap: Record<string, string> = {
  low: "safe",
  medium: "warning",
  high: "danger",
  critical: "danger",
};

const riskLabelMap: Record<string, string> = {
  low: "낮음",
  medium: "보통",
  high: "높음",
  critical: "심각",
};

function formatPercent(value: number) {
  return `${(value * 100).toFixed(0)}%`;
}

function formatScore(value: number) {
  return value.toFixed(2);
}

export function RiskSummaryCard({
  riskLevel,
  riskScore,
  confidence,
  confidenceMargin,
  summaryText,
  status = "ready",
  isLoading = false,
  error,
}: Props) {
  const normalizedRiskLevel = riskLevel.toLowerCase();
  const state = error ? "error" : isLoading ? "loading" : status;
  const riskTone = riskToneMap[normalizedRiskLevel] ?? "neutral";
  const riskLabel = riskLabelMap[normalizedRiskLevel] ?? riskLevel.toUpperCase();

  return (
    <section className="card panel-section risk-summary">
      <div className="card__header">
        <div>
          <div className="badge">위험도 요약</div>
          <h3 className="card__title">의사결정 우선순위</h3>
        </div>
        <span className={`status-chip status-chip--${state}`}>
          {state === "loading" ? "불러오는 중" : state === "error" ? "검토 필요" : "분석 완료"}
        </span>
      </div>

      {state === "error" ? (
        <div className="state-banner state-banner--error">{error ?? "위험도 분석 결과를 불러오지 못했습니다."}</div>
      ) : state === "loading" ? (
        <div className="state-banner state-banner--loading">위험도와 신뢰도를 계산하고 있습니다.</div>
      ) : null}

      <div className="risk-summary__hero">
        <div>
          <p className="eyebrow">현재 판정</p>
          <strong className={`risk-summary__level risk-summary__level--${riskTone}`}>{riskLabel}</strong>
        </div>
        <p className="risk-summary__copy">
          현장 대응 여부를 빠르게 판단할 수 있도록 위험도와 모델 확신도를 함께 제공합니다.
        </p>
      </div>

      <div className="metric-grid risk-summary__metrics">
        <div className="metric-card">
          <span className="metric-card__label">위험 점수</span>
          <strong className="metric-card__value">{formatScore(riskScore)}</strong>
          <span className="metric-card__hint">0~1 범위 정규화</span>
        </div>
        <div className="metric-card">
          <span className="metric-card__label">판독 신뢰도</span>
          <strong className="metric-card__value">{formatPercent(confidence)}</strong>
          <span className="metric-card__hint">
            모델 확신도 기준{typeof confidenceMargin === "number" ? ` · 오차폭 ±${(confidenceMargin * 100).toFixed(1)}%p` : ""}
          </span>
        </div>
      </div>

      {summaryText ? <p className="card__lead">{summaryText}</p> : null}
    </section>
  );
}
