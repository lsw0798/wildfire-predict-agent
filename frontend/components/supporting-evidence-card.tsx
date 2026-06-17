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
      items: keyFactors,
      emptyMessage: "현재 표시할 핵심 요인이 없습니다.",
    },
    {
      key: "xai-reasons",
      badge: "XAI 설명",
      title: "모델 판단 해석",
      items: xaiReasons,
      emptyMessage: "백엔드에서 아직 추가 설명 필드를 반환하지 않았습니다.",
    },
    {
      key: "reviewed-signals",
      badge: "검토 신호",
      title: "이번 분석에서 확인한 입력",
      items: reviewedSignals,
      emptyMessage: "검토된 신호 목록이 제공되지 않았습니다.",
    },
  ];

  return (
    <section className="card panel-section supporting-evidence">
      <div className="card__header">
        <div>
          <div className="badge">설명 가능성</div>
          <h3 className="card__title">사용자용 판단 근거</h3>
        </div>
        <span className="status-chip status-chip--ready">XAI 표시</span>
      </div>

      <div className="supporting-evidence__grid">
        {groups.map((group) => (
          <div key={group.key} className="supporting-evidence__group">
            <div className="badge">{group.badge}</div>
            <h4>{group.title}</h4>
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
