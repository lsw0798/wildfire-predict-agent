type RadiusPoints = {
  north: { lat: number; lon: number };
  south: { lat: number; lon: number };
  east: { lat: number; lon: number };
  west: { lat: number; lon: number };
};

type Props = {
  radiusKm: number;
  confidenceMargin: number;
  dataQualitySummary: string;
  radiusPoints?: RadiusPoints | null;
};

function formatDistance(value: number) {
  return `${value.toFixed(value >= 10 ? 0 : 1)}km`;
}

function formatPercent(value: number) {
  return `±${(value * 100).toFixed(1)}%p`;
}

function formatCoordinate(value: number) {
  return value.toFixed(4);
}

export function AnalysisCoverageCard({ radiusKm, confidenceMargin, dataQualitySummary, radiusPoints }: Props) {
  const coverageRows = radiusPoints
    ? [
        { label: "북쪽 경계", value: `${formatCoordinate(radiusPoints.north.lat)}, ${formatCoordinate(radiusPoints.north.lon)}` },
        { label: "남쪽 경계", value: `${formatCoordinate(radiusPoints.south.lat)}, ${formatCoordinate(radiusPoints.south.lon)}` },
        { label: "동쪽 경계", value: `${formatCoordinate(radiusPoints.east.lat)}, ${formatCoordinate(radiusPoints.east.lon)}` },
        { label: "서쪽 경계", value: `${formatCoordinate(radiusPoints.west.lat)}, ${formatCoordinate(radiusPoints.west.lon)}` },
      ]
    : [];

  return (
    <section className="card panel-section coverage-card">
      <div className="card__header">
        <div>
          <div className="badge">분석 범위</div>
          <h3 className="card__title">반경 및 데이터 품질</h3>
        </div>
        <span className="status-chip status-chip--idle">{formatDistance(radiusKm)}</span>
      </div>

      <div className="metric-grid">
        <div className="metric-card">
          <span className="metric-card__label">선택 반경</span>
          <strong className="metric-card__value">{formatDistance(radiusKm)}</strong>
          <span className="metric-card__hint">지도 원형 오버레이로 시각화</span>
        </div>
        <div className="metric-card">
          <span className="metric-card__label">신뢰도 오차폭</span>
          <strong className="metric-card__value">{formatPercent(confidenceMargin)}</strong>
          <span className="metric-card__hint">모델 판정 변동 범위</span>
        </div>
      </div>

      <div className="coverage-card__summary">
        <span className="eyebrow">데이터 품질 요약</span>
        <p>{dataQualitySummary}</p>
      </div>

      {coverageRows.length > 0 ? (
        <div className="coverage-card__bounds">
          <span className="eyebrow">반경 경계 좌표</span>
          <div className="coverage-card__grid">
            {coverageRows.map((row) => (
              <div key={row.label} className="coverage-card__bound">
                <strong>{row.label}</strong>
                <span>{row.value}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
