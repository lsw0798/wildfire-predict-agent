import { AnalysisDashboard } from "../../components/analysis-dashboard";
import { buildAnalyzeNavigationState } from "../../lib/analyze-navigation";

type AnalyzePageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function AnalyzePage({ searchParams }: AnalyzePageProps) {
  const resolvedSearchParams = (await searchParams) ?? {};
  const urlSearchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(resolvedSearchParams)) {
    if (typeof value === "string") {
      urlSearchParams.set(key, value);
      continue;
    }

    if (Array.isArray(value) && value.length > 0) {
      urlSearchParams.set(key, value[0] ?? "");
    }
  }

  const navigationState = buildAnalyzeNavigationState(urlSearchParams);

  return (
    <AnalysisDashboard
      initialAutoRunKey={navigationState.autoRunKey}
      initialAutoRunRequested={navigationState.autoRunRequested}
      initialFormState={navigationState.formState}
    />
  );
}
