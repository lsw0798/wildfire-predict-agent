const allowedUserTypes = new Set(["공무원", "진압대원", "구조요원", "시민"]);

export const DEFAULT_ANALYSIS_FORM_STATE = {
  lat: "37.110673",
  lon: "127.297152",
  userType: "공무원",
  radiusKm: "5",
};

export type AnalysisFormState = typeof DEFAULT_ANALYSIS_FORM_STATE & {
  sourceLabel: string | null;
};

export type AnalyzeNavigationState = {
  formState: AnalysisFormState;
  autoRunRequested: boolean;
  autoRunKey: string | null;
};

export type AnalyzeHrefInput = {
  province: string;
  city: string;
  lat: number;
  lon: number;
  radiusKm?: number;
  autoRun?: boolean;
};

function isFiniteNumber(value: string | null) {
  return value !== null && Number.isFinite(Number(value));
}

function isPositiveNumber(value: string | null) {
  return isFiniteNumber(value) && Number(value) > 0;
}

function buildAutoRunKey(formState: AnalysisFormState) {
  return [formState.lat, formState.lon, formState.radiusKm, formState.userType, formState.sourceLabel ?? ""].join("|");
}

export function buildAnalyzeHref({
  province,
  city,
  lat,
  lon,
  radiusKm = Number(DEFAULT_ANALYSIS_FORM_STATE.radiusKm),
  autoRun = false,
}: AnalyzeHrefInput) {
  const searchParams = new URLSearchParams({
    lat: lat.toFixed(6),
    lon: lon.toFixed(6),
    radiusKm: radiusKm.toString(),
    source: `${province} ${city}`.trim(),
  });

  if (autoRun) {
    searchParams.set("autoRun", "1");
  }

  return `/analyze?${searchParams.toString()}`;
}

export function buildInitialAnalysisFormState(searchParams: URLSearchParams | ReadonlyURLSearchParams): AnalysisFormState {
  return buildAnalyzeNavigationState(searchParams).formState;
}

export function buildAnalyzeNavigationState(searchParams: URLSearchParams | ReadonlyURLSearchParams): AnalyzeNavigationState {
  const lat = searchParams.get("lat");
  const lon = searchParams.get("lon");
  const radiusKm = searchParams.get("radiusKm");
  const userType = searchParams.get("userType");
  const source = searchParams.get("source");

  const formState: AnalysisFormState = {
    lat: isFiniteNumber(lat) ? Number(lat).toFixed(6) : DEFAULT_ANALYSIS_FORM_STATE.lat,
    lon: isFiniteNumber(lon) ? Number(lon).toFixed(6) : DEFAULT_ANALYSIS_FORM_STATE.lon,
    radiusKm: isPositiveNumber(radiusKm) ? Number(radiusKm).toString() : DEFAULT_ANALYSIS_FORM_STATE.radiusKm,
    userType: userType && allowedUserTypes.has(userType) ? userType : DEFAULT_ANALYSIS_FORM_STATE.userType,
    sourceLabel: source?.trim() ? source.trim() : null,
  };

  const autoRunRequested = searchParams.get("autoRun") === "1";

  return {
    formState,
    autoRunRequested,
    autoRunKey: autoRunRequested ? buildAutoRunKey(formState) : null,
  };
}

type ReadonlyURLSearchParams = Pick<URLSearchParams, "get">;
