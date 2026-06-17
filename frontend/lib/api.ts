export type AnalyzeRequest = {
  lat: number;
  lon: number;
  user_type: string;
};

export type AnalyzeResponse = {
  risk_level: string;
  risk_score: number;
  false_positive_risk: string;
  confidence: number;
  key_factors: string[];
  recommended_actions: string[];
  uncertainty_notes: string[];
};

export async function analyzeRisk(payload: AnalyzeRequest): Promise<AnalyzeResponse> {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const response = await fetch(`${baseUrl}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("분석 요청에 실패했습니다.");
  }

  return response.json();
}
