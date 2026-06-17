type Props = {
  selectedTools?: string[];
  selectionReason?: string | null;
  selectionMode?: string | null;
};

const toolLabelMap: Record<string, string> = {
  historical: "과거 이력",
  realtime: "실시간 맥락",
};

const modeLabelMap: Record<string, string> = {
  full: "전체 조회",
  selective: "선별 조회",
  rule_fallback: "규칙 기반 계속 분석",
};

function formatToolLabel(tool: string) {
  return toolLabelMap[tool] ?? tool;
}

function formatModeLabel(mode: string) {
  return modeLabelMap[mode] ?? mode;
}

function isQuotaFallback(selectionMode?: string | null, selectionReason?: string | null) {
  if (selectionMode !== "rule_fallback") {
    return false;
  }

  const normalizedReason = selectionReason?.toLowerCase() ?? "";
  return (
    normalizedReason.includes("openai") &&
    (normalizedReason.includes("크레딧") ||
      normalizedReason.includes("한도") ||
      normalizedReason.includes("quota") ||
      normalizedReason.includes("429"))
  );
}

export function SelectionMetadataCard({
  selectedTools = [],
  selectionReason,
  selectionMode,
}: Props) {
  const hasTools = selectedTools.length > 0;
  const hasReason = typeof selectionReason === "string" && selectionReason.trim().length > 0;
  const hasMode = typeof selectionMode === "string" && selectionMode.trim().length > 0;
  const showQuotaFallbackBanner = isQuotaFallback(selectionMode, selectionReason);

  if (!hasTools && !hasReason && !hasMode) {
    return null;
  }

  return (
    <section className="card panel-section selection-metadata">
      <div className="card__header">
        <div>
          <div className="badge">선택 메타데이터</div>
          <h3 className="card__title">조회 소스 판단 근거</h3>
        </div>
        {hasMode ? <span className="status-chip status-chip--idle">{formatModeLabel(selectionMode!)}</span> : null}
      </div>

      {showQuotaFallbackBanner ? (
        <div className="state-banner state-banner--idle selection-metadata__notice">
          현재 OpenAI API 크레딧/한도 문제로 LLM 소스 선택은 건너뛰었지만, 규칙 기반 fallback으로 분석은 계속 진행했습니다.
        </div>
      ) : null}

      {hasTools ? (
        <div className="selection-metadata__group">
          <span className="eyebrow">선택된 소스</span>
          <div className="selection-metadata__badges">
            {selectedTools.map((tool) => (
              <span key={tool} className="severity-pill severity-pill--neutral">
                {formatToolLabel(tool)}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {hasReason ? (
        <div className="selection-metadata__group">
          <span className="eyebrow">선택 이유</span>
          <p className="selection-metadata__reason">{selectionReason}</p>
        </div>
      ) : null}
    </section>
  );
}
