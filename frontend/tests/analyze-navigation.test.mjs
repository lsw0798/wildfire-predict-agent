import assert from "node:assert/strict";
import test from "node:test";

import {
  buildAnalyzeHref,
  buildAnalyzeNavigationState,
  buildInitialAnalysisFormState,
  DEFAULT_ANALYSIS_FORM_STATE,
} from "../lib/analyze-navigation.ts";

test("buildAnalyzeHref encodes watchpoint coordinates, radius, and source label into analyze URL", () => {
  const href = buildAnalyzeHref({
    city: "홍천군",
    lat: 37.6972,
    lon: 127.8889,
    province: "강원특별자치도",
    radiusKm: 10,
  });

  assert.equal(
    href,
    "/analyze?lat=37.697200&lon=127.888900&radiusKm=10&source=%EA%B0%95%EC%9B%90%ED%8A%B9%EB%B3%84%EC%9E%90%EC%B9%98%EB%8F%84+%ED%99%8D%EC%B2%9C%EA%B5%B0",
  );
});

test("buildAnalyzeHref adds autoRun flag only when requested", () => {
  const href = buildAnalyzeHref({
    city: "홍천군",
    lat: 37.6972,
    lon: 127.8889,
    province: "강원특별자치도",
    radiusKm: 10,
    autoRun: true,
  });

  assert.equal(
    href,
    "/analyze?lat=37.697200&lon=127.888900&radiusKm=10&source=%EA%B0%95%EC%9B%90%ED%8A%B9%EB%B3%84%EC%9E%90%EC%B9%98%EB%8F%84+%ED%99%8D%EC%B2%9C%EA%B5%B0&autoRun=1",
  );
});

test("buildInitialAnalysisFormState prefers valid query params and preserves defaults otherwise", () => {
  const searchParams = new URLSearchParams({
    lat: "35.179554",
    lon: "129.075642",
    radiusKm: "20",
    userType: "구조요원",
    source: "부산광역시 중구",
  });

  const state = buildInitialAnalysisFormState(searchParams);

  assert.deepEqual(state, {
    lat: "35.179554",
    lon: "129.075642",
    radiusKm: "20",
    sourceLabel: "부산광역시 중구",
    userType: "구조요원",
  });
});

test("buildInitialAnalysisFormState falls back to defaults when query params are invalid", () => {
  const searchParams = new URLSearchParams({
    lat: "north",
    lon: "east",
    radiusKm: "0",
    userType: "외부인",
    source: "",
  });

  const state = buildInitialAnalysisFormState(searchParams);

  assert.deepEqual(state, {
    ...DEFAULT_ANALYSIS_FORM_STATE,
    sourceLabel: null,
  });
});

test("buildAnalyzeNavigationState requests auto-run only for explicit autoRun=1 links", () => {
  const autoRunSearchParams = new URLSearchParams({
    lat: "37.697200",
    lon: "127.888900",
    radiusKm: "10",
    source: "강원특별자치도 홍천군",
    autoRun: "1",
  });
  const manualSearchParams = new URLSearchParams({
    lat: "37.697200",
    lon: "127.888900",
    radiusKm: "10",
    source: "강원특별자치도 홍천군",
  });

  const autoRunState = buildAnalyzeNavigationState(autoRunSearchParams);
  const manualState = buildAnalyzeNavigationState(manualSearchParams);

  assert.equal(autoRunState.autoRunRequested, true);
  assert.equal(autoRunState.autoRunKey, "37.697200|127.888900|10|공무원|강원특별자치도 홍천군");
  assert.equal(manualState.autoRunRequested, false);
  assert.equal(manualState.autoRunKey, null);
});
