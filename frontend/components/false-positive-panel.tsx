type Props = {
  level: string;
  notes: string[];
  summaryText?: string;
  status?: "idle" | "loading" | "ready" | "error";
  isLoading?: boolean;
  error?: string | null;
};

const falsePositiveToneMap: Record<string, string> = {
  low: "safe",
  medium: "warning",
  high: "danger",
  critical: "danger",
};

const falsePositiveLabelMap: Record<string, string> = {
  low: "낮음",
  medium: "보통",
  high: "높음",
  critical: "심각",
};

export function FalsePositivePanel({
  level,
  notes,
  summaryText,
  status = "ready",
  isLoading = false,
  error,
}: Props) {
  const normalizedLevel = level.toLowerCase();
  const state = error ? "error" : isLoading ? "loading" : status;
  const tone = falsePositiveToneMap[normalizedLevel] ?? "neutral";
  const label = falsePositiveLabelMap[normalizedLevel] ?? level;

  return (
    <section className="card panel-section false-positive">
      <div className="card__header">
        <div>
          <div className="badge">오탐 검토</div>
          <h3 className="card__title">현장 재확인 포인트</h3>
        </div>
        <span className={`status-chip status-chip--${state}`}>
          {state === "loading" ? "검토 중" : state === "error" ? "주의" : "체크 완료"}
        </span>
      </div>

      <div className="inline-summary">
        <span className="eyebrow">오탐 가능성</span>
        <strong className={`severity-pill severity-pill--${tone}`}>{label}</strong>
      </div>

      {state === "error" ? (
        <div className="state-banner state-banner--error">{error ?? "오탐 검토 메모를 불러오지 못했습니다."}</div>
      ) : state === "loading" ? (
        <div className="state-banner state-banner--loading">
          위성·기상·현장 맥락을 기준으로 오탐 가능성을 다시 검토합니다.
        </div>
      ) : null}

      {summaryText ? <p className="card__lead">{summaryText}</p> : null}

      {notes.length > 0 ? (
        <ul className="list rich-list false-positive__notes">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : (
        <div className="empty-list">현재 추가 확인이 필요한 오탐 메모는 없습니다.</div>
      )}
    </section>
  );
}
