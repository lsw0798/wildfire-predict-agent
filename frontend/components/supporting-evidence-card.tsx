type Props = {
  keyFactors: string[];
  xaiReasons: string[];
  reviewedSignals: string[];
};

export function SupportingEvidenceCard({ keyFactors, xaiReasons, reviewedSignals }: Props) {
  const groups = [
    {
      key: "key-factors",
      badge: "주요 근거",
      title: "위험도 상승 요인",
      description: "이번 위치에서 위험도를 끌어올린 핵심 요소입니다.",
      items: keyFactors,
      emptyMessage: "현재 표시할 핵심 요인이 없습니다.",
    },
    {
      key: "xai-reasons",
      badge: "XAI 설명",
      title: "판단 해석",
      description: "모델/규칙이 어떤 맥락을 근거로 판단했는지 설명합니다.",
      items: xaiReasons,
      emptyMessage: "백엔드에서 아직 추가 설명 필드를 반환하지 않았습니다.",
    },
    {
      key: "reviewed-signals",
      badge: "검토 신호",
      title: "이번 분석에서 확인한 입력",
      description: "위험도와 오탐 가능성을 검토할 때 사용한 입력 신호입니다.",
      items: reviewedSignals,
      emptyMessage: "검토된 신호 목록이 제공되지 않았습니다.",
    },
  ];

  return (
    <section className="card panel-section supporting-evidence">
      <div className="card__header supporting-evidence__header">
        <div>
          <div className="badge">설명 가능성</div>
          <h3 className="card__title">사용자용 판단 근거</h3>
        </div>
        <span className="status-chip status-chip--ready">XAI 표시</span>
      </div>

      <p className="card__lead supporting-evidence__lead">
        결과를 바로 믿기보다, 어떤 근거와 입력이 반영됐는지 확인할 수 있도록 설명을 묶어서 제공합니다.
      </p>

      <div className="supporting-evidence__stack">
        {groups.map((group) => (
          <div key={group.key} className="supporting-evidence__group">
            <div className="supporting-evidence__group-header">
              <div className="badge">{group.badge}</div>
              <div>
                <h4>{group.title}</h4>
                <p>{group.description}</p>
              </div>
            </div>
            {group.items.length > 0 ? (
              <ul className="list rich-list">
                {group.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <div className="empty-list">{group.emptyMessage}</div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
