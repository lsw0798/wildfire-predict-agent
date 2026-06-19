export type ForestHeatmapPoint = {
  id: string;
  province: string;
  city: string;
  lat: number;
  lon: number;
  risk_score: number;
  risk_level: "low" | "medium" | "high" | "critical" | string;
  confidence: number;
  confidence_margin: number;
  review_required: boolean;
  incident_count: number;
  latest_year?: number | null;
  top_cause?: string | null;
  circle_radius_m: number;
  key_factors: string[];
};

export type ForestHeatmapResponse = {
  generated_at: string;
  metric: string;
  resolution: number;
  total_records: number;
  forest_records: number;
  filtered_records: number;
  points: ForestHeatmapPoint[];
};

export type ForestHeatmapFetchResult =
  | { status: "ready"; heatmap: ForestHeatmapResponse }
  | { status: "unavailable"; message: string }
  | { status: "error"; message: string };

function buildForestHeatmapUrl() {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";
  const url = new URL(`${baseUrl}/api/monitoring/forest-heatmap`, typeof window === "undefined" ? "http://localhost" : window.location.origin);
  url.searchParams.set("limit", "1000");
  url.searchParams.set("resolution", "0.1");
  if (!baseUrl) {
    return `${url.pathname}${url.search}`;
  }
  return url.toString();
}

export async function fetchForestHeatmap(signal?: AbortSignal): Promise<ForestHeatmapFetchResult> {
  try {
    const response = await fetch(buildForestHeatmapUrl(), {
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal,
    });

    if (response.status === 404 || response.status === 501) {
      return {
        status: "unavailable",
        message: "산림 히트맵 엔드포인트가 아직 준비되지 않았습니다.",
      };
    }

    if (!response.ok) {
      const responseText = await response.text();
      return {
        status: "error",
        message: responseText.trim() || "산림 히트맵 데이터를 불러오지 못했습니다.",
      };
    }

    return {
      status: "ready",
      heatmap: (await response.json()) as ForestHeatmapResponse,
    };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return { status: "unavailable", message: "산림 히트맵 요청이 취소되었습니다." };
    }
    return {
      status: "error",
      message: error instanceof Error ? error.message : "산림 히트맵을 불러오는 중 알 수 없는 오류가 발생했습니다.",
    };
  }
}
