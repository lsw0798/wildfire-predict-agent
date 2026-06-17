type Props = {
  actions: string[];
  status?: "idle" | "loading" | "ready" | "error";
  isLoading?: boolean;
  error?: string | null;
};

export function ActionGuide({
  actions,
  status = "ready",
  isLoading = false,
  error,
}: Props) {
  const state = error ? "error" : isLoading ? "loading" : status;

  return (
    <section className="card panel-section action-guide">
      <div className="card__header">
        <div>
          <div className="badge">권장 행동</div>
          <h3 className="card__title">대응 체크리스트</h3>
        </div>
        <span className={`status-chip status-chip--${state}`}>{state === "loading" ? "정리 중" : state === "error" ? "재검토 필요" : "즉시 실행"}</span>
      </div>

      {state === "error" ? (
        <div className="state-banner state-banner--error">{error ?? "권장 행동 목록을 생성하지 못했습니다."}</div>
      ) : state === "loading" ? (
        <div className="state-banner state-banner--loading">위험도와 사회 인프라 상황에 맞춘 행동 우선순위를 정리하고 있습니다.</div>
      ) : null}

      {actions.length > 0 ? (
        <ol className="list rich-list rich-list--ordered action-guide__list">
          {actions.map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ol>
      ) : (
        <div className="empty-list">아직 제안된 대응 행동이 없습니다.</div>
      )}
    </section>
  );
}
