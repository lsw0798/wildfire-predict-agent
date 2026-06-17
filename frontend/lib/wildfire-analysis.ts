export type AnalyzeRequest = {
  lat: number;
  lon: number;
  user_type: string;
  radius_km?: number;
};

export type AnalyzeResponse = {
  risk_level: string;
  risk_score: number;
  false_positive_risk: string;
  confidence: number;
  confidence_margin: number;
  analysis_radius_km: number;
  radius_points: {
    north: { lat: number; lon: number };
    south: { lat: number; lon: number };
    east: { lat: number; lon: number };
    west: { lat: number; lon: number };
  };
  key_factors: string[];
  recommended_actions: string[];
  risk_summary_text: string;
  false_positive_summary_text: string;
  xai_reasons: string[];
  reviewed_signals: string[];
  data_quality_summary: string;
  uncertainty_notes: string[];
  selected_tools?: string[];
  selection_reason?: string;
  selection_mode?: string;
};

function buildAnalyzeUrl() {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";
  return `${baseUrl}/api/analyze`;
}

export async function fetchWildfireAnalysis(
  payload: AnalyzeRequest,
  signal?: AbortSignal,
): Promise<AnalyzeResponse> {
  const response = await fetch(buildAnalyzeUrl(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });

  const responseText = await response.text();

  if (!response.ok) {
    let message = "산불 분석 요청에 실패했습니다.";

    if (responseText.trim()) {
      try {
        const data = JSON.parse(responseText) as { detail?: string };
        if (typeof data.detail === "string" && data.detail.trim()) {
          message = data.detail;
        } else {
          message = responseText;
        }
      } catch {
        message = responseText;
      }
    }

    throw new Error(message);
  }

  return JSON.parse(responseText) as AnalyzeResponse;
}
