export type MonitoringWatchpoint = {
  id: string;
  province: string;
  city: string;
  lat: number;
  lon: number;
  incident_count: number;
  latest_year?: number | null;
  top_cause?: string | null;
  priority_score: number;
  priority_label: "low" | "medium" | "high" | string;
};

export type MonitoringSummary = {
  generated_at: string;
  total_records: number;
  watchpoints: MonitoringWatchpoint[];
};

export type MonitoringFetchResult =
  | { status: "ready"; summary: MonitoringSummary }
  | { status: "unavailable"; message: string }
  | { status: "error"; message: string };

function buildMonitoringUrl() {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";
  return `${baseUrl}/api/monitoring/summary`;
}

export async function fetchMonitoringSummary(signal?: AbortSignal): Promise<MonitoringFetchResult> {
  try {
    const response = await fetch(buildMonitoringUrl(), {
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal,
    });

    if (response.status === 404 || response.status === 501) {
      return {
        status: "unavailable",
        message: "백엔드 모니터링 요약 엔드포인트가 아직 준비되지 않았습니다.",
      };
    }

    if (!response.ok) {
      const responseText = await response.text();
      return {
        status: "error",
        message: responseText.trim() || "모니터링 요약을 불러오지 못했습니다.",
      };
    }

    return {
      status: "ready",
      summary: (await response.json()) as MonitoringSummary,
    };
  } catch (error) {
    return {
      status: "error",
      message: error instanceof Error ? error.message : "모니터링 요약을 불러오는 중 알 수 없는 오류가 발생했습니다.",
    };
  }
}
