import { expect, test } from "@playwright/test";

const monitoringSummary = {
  generated_at: "2026-06-16T00:00:00Z",
  total_records: 3,
  watchpoints: [
    {
      id: "gyeonggi-yangpyeong",
      province: "경기도",
      city: "양평군",
      lat: 37.5178,
      lon: 127.538,
      incident_count: 126,
      latest_year: 2023,
      top_cause: "기타",
      priority_score: 1266,
      priority_label: "high",
    },
    {
      id: "gyeonggi-namyangju",
      province: "경기도",
      city: "남양주시",
      lat: 37.6589,
      lon: 127.2386,
      incident_count: 113,
      latest_year: 2023,
      top_cause: "입산자실화",
      priority_score: 1138,
      priority_label: "high",
    },
    {
      id: "gyeonggi-hwaseong",
      province: "경기도",
      city: "화성시",
      lat: 37.1885,
      lon: 126.8429,
      incident_count: 113,
      latest_year: 2023,
      top_cause: "쓰레기소각",
      priority_score: 1137,
      priority_label: "high",
    },
  ],
};

const analysisResponse = {
  risk_level: "low",
  risk_score: 0.06,
  false_positive_risk: "low",
  confidence: 0.63,
  confidence_margin: 0.11,
  analysis_radius_km: 10,
  radius_points: {
    north: { lat: 37.6077, lon: 127.538 },
    south: { lat: 37.4279, lon: 127.538 },
    east: { lat: 37.5178, lon: 127.6514 },
    west: { lat: 37.5178, lon: 127.4246 },
  },
  key_factors: ["장기 가뭄", "산지 인접 이력"],
  recommended_actions: ["현장 순찰 유지", "산불 취약 구역 안내 방송 점검"],
  risk_summary_text: "현재 위치는 반경 10.0km 기준으로 산불 위험이 낮은 편입니다.",
  false_positive_summary_text: "오탐 가능성은 낮지만 단일 신호만으로 확정하지 않습니다.",
  xai_reasons: ["위험 판단 근거: 장기 가뭄"],
  reviewed_signals: ["과거 데이터 출처: live", "실시간 데이터 출처: fallback"],
  data_quality_summary: "현재 신뢰도는 0.63이며 일부 항목은 추정값을 포함합니다.",
  uncertainty_notes: ["graph completed"],
  selected_tools: ["historical", "realtime"],
  selection_reason: "규칙 기반 판단으로 두 소스를 모두 사용했습니다.",
  selection_mode: "rule_fallback",
};

test.describe("monitor to analyze flow", () => {
  test("Top 10 full-card click navigates with autoRun and shows loading before results", async ({ page }) => {
    await page.route("**/api/monitoring/summary", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(monitoringSummary),
      });
    });

    let analyzePayload: Record<string, unknown> | null = null;
    await page.route("**/api/analyze", async (route) => {
      analyzePayload = route.request().postDataJSON() as Record<string, unknown>;
      await page.waitForTimeout(300);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(analysisResponse),
      });
    });

    await page.goto("/");

    const topCard = page.getByRole("link", { name: /1\. 경기도 양평군/ });
    await expect(topCard).toBeVisible();
    await topCard.click();

    await expect(page).toHaveURL(/\/analyze\?/);
    await expect(page).toHaveURL(/autoRun=1/);
    await expect(page.getByText("모니터링 페이지에서 전달된 위치를 기준으로 자동 분석을 시작했습니다.")).toBeVisible();
    await expect(page.getByText("분석 결과 준비 중")).toBeVisible();
    await expect(page.getByTestId("analysis-skeleton-card").first()).toBeVisible();

    await expect(page.getByRole("heading", { name: "의사결정 우선순위" })).toBeVisible();
    await expect(page.getByText("현재 위치는 반경 10.0km 기준으로 산불 위험이 낮은 편입니다.")).toBeVisible();

    expect(analyzePayload).toEqual({
      lat: 37.5178,
      lon: 127.538,
      radius_km: 10,
      user_type: "공무원",
    });
  });

  test("Top 5 link pre-fills analyze form without auto-running", async ({ page }) => {
    await page.route("**/api/monitoring/summary", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(monitoringSummary),
      });
    });

    let analyzeRequestCount = 0;
    await page.route("**/api/analyze", async (route) => {
      analyzeRequestCount += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(analysisResponse),
      });
    });

    await page.goto("/");
    await page.getByRole("link", { name: "좌표 자동 입력으로 분석 열기" }).first().click();

    await expect(page).toHaveURL(/\/analyze\?/);
    await expect(page).not.toHaveURL(/autoRun=1/);
    await expect(page.getByLabel("위도")).toHaveValue("37.517800");
    await expect(page.getByLabel("경도")).toHaveValue("127.538000");
    await expect(page.getByLabel("분석 반경 \(km\)")).toHaveValue("10");
    await expect(page.getByText("좌표·반경·사용자 유형을 입력한 뒤 분석을 실행하면 결과가 여기에 표시됩니다.")).toBeVisible();
    expect(analyzeRequestCount).toBe(0);

    await page.getByRole("button", { name: "분석 실행" }).click();
    await expect(page.getByRole("heading", { name: "의사결정 우선순위" })).toBeVisible();
    expect(analyzeRequestCount).toBe(1);
  });
});
