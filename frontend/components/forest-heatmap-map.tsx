"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { buildAnalyzeHref } from "../lib/analyze-navigation";
import { ForestHeatmapFetchResult, ForestHeatmapPoint, fetchForestHeatmap } from "../lib/forest-heatmap";

type LoaderState = "idle" | "loading" | "ready" | "missing-key" | "failed";

type KakaoLatLng = {
  getLat: () => number;
  getLng: () => number;
};

type KakaoMap = {
  setCenter: (latLng: KakaoLatLng) => void;
  relayout?: () => void;
};

type KakaoMarker = {
  setMap: (map: KakaoMap | null) => void;
  setPosition?: (position: KakaoLatLng) => void;
};

type KakaoCircle = {
  setMap: (map: KakaoMap | null) => void;
  setPosition?: (position: KakaoLatLng) => void;
  setRadius?: (radius: number) => void;
};

declare global {
  interface Window {
    kakao?: {
      maps: {
        load: (callback: () => void) => void;
        LatLng: new (lat: number, lng: number) => KakaoLatLng;
        Size: new (width: number, height: number) => unknown;
        Point: new (x: number, y: number) => unknown;
        Map: new (container: HTMLElement, options: Record<string, unknown>) => KakaoMap;
        Marker: new (options: Record<string, unknown>) => KakaoMarker;
        MarkerImage: new (src: string, size: unknown, options?: Record<string, unknown>) => unknown;
        Circle: new (options: Record<string, unknown>) => KakaoCircle;
        event: {
          addListener: (target: unknown, type: string, handler: (mouseEvent: { latLng: KakaoLatLng }) => void) => void;
        };
      };
    };
  }
}

const KAKAO_SCRIPT_ID = "kakao-maps-sdk";
const KAKAO_KEY = process.env.NEXT_PUBLIC_KAKAO_JAVASCRIPT_KEY;
const KOREA_CENTER = { lat: 36.35, lng: 127.85 };
let kakaoMapsLoaderPromise: Promise<NonNullable<Window["kakao"]>> | null = null;

function loadKakaoMapsScript(): Promise<NonNullable<Window["kakao"]>> {
  if (kakaoMapsLoaderPromise) {
    return kakaoMapsLoaderPromise;
  }

  kakaoMapsLoaderPromise = new Promise((resolve, reject) => {
    if (typeof window === "undefined") {
      reject(new Error("window is not available"));
      return;
    }

    if (!KAKAO_KEY) {
      reject(new Error("NEXT_PUBLIC_KAKAO_JAVASCRIPT_KEY is not configured"));
      return;
    }

    const ready = () => {
      if (!window.kakao?.maps) {
        reject(new Error("Kakao Maps SDK did not initialize"));
        return;
      }
      window.kakao.maps.load(() => {
        if (!window.kakao) {
          reject(new Error("Kakao Maps global is unavailable after load"));
          return;
        }
        resolve(window.kakao);
      });
    };

    if (window.kakao?.maps) {
      ready();
      return;
    }

    const existingScript = document.getElementById(KAKAO_SCRIPT_ID) as HTMLScriptElement | null;
    if (existingScript) {
      if (existingScript.dataset.loaded === "true") {
        ready();
        return;
      }
      existingScript.addEventListener("load", ready, { once: true });
      existingScript.addEventListener("error", () => reject(new Error("Kakao Maps SDK failed to load")), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.id = KAKAO_SCRIPT_ID;
    script.async = true;
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_KEY}&autoload=false`;
    script.onload = () => {
      script.dataset.loaded = "true";
      ready();
    };
    script.onerror = () => reject(new Error("Kakao Maps SDK failed to load"));
    document.head.appendChild(script);
  });

  return kakaoMapsLoaderPromise;
}

function getRiskColor(score: number) {
  if (score >= 0.75) {
    return "#eb5757";
  }
  if (score >= 0.55) {
    return "#f2994a";
  }
  if (score >= 0.35) {
    return "#f2c94c";
  }
  return "#2f80ed";
}

function getRiskLabel(level: string) {
  const labels: Record<string, string> = {
    critical: "매우 높음",
    high: "높음",
    medium: "중간",
    low: "낮음",
  };
  return labels[level] ?? level;
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatDateLabel(value?: string) {
  if (!value) {
    return "업데이트 정보 없음";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ko-KR", { dateStyle: "short", timeStyle: "short" }).format(date);
}

export function ForestHeatmapMap() {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<KakaoMap | null>(null);
  const kakaoRef = useRef<NonNullable<Window["kakao"]> | null>(null);
  const circlesRef = useRef<KakaoCircle[]>([]);
  const [loaderState, setLoaderState] = useState<LoaderState>(KAKAO_KEY ? "idle" : "missing-key");
  const [heatmapResult, setHeatmapResult] = useState<ForestHeatmapFetchResult>({
    status: "unavailable",
    message: "산림 히트맵 데이터를 아직 요청하지 않았습니다.",
  });
  const [selectedPoint, setSelectedPoint] = useState<ForestHeatmapPoint | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchForestHeatmap(controller.signal).then((result) => setHeatmapResult(result));
    return () => controller.abort();
  }, []);

  const points = useMemo(() => {
    if (heatmapResult.status !== "ready") {
      return [];
    }
    return heatmapResult.heatmap.points;
  }, [heatmapResult]);

  const highRiskCount = useMemo(() => points.filter((point) => point.risk_score >= 0.55).length, [points]);
  const reviewRequiredCount = useMemo(() => points.filter((point) => point.review_required).length, [points]);

  useEffect(() => {
    if (!KAKAO_KEY) {
      setLoaderState("missing-key");
      return;
    }

    let cancelled = false;
    setLoaderState("loading");

    loadKakaoMapsScript()
      .then((kakao) => {
        if (cancelled || !mapContainerRef.current || mapRef.current) {
          return;
        }
        kakaoRef.current = kakao;
        const map = new kakao.maps.Map(mapContainerRef.current, {
          center: new kakao.maps.LatLng(KOREA_CENTER.lat, KOREA_CENTER.lng),
          level: 13,
        });
        mapRef.current = map;

        const relayout = () => {
          map.relayout?.();
          map.setCenter(new kakao.maps.LatLng(KOREA_CENTER.lat, KOREA_CENTER.lng));
        };
        requestAnimationFrame(relayout);
        window.setTimeout(() => {
          if (!cancelled && mapRef.current === map) {
            relayout();
          }
        }, 160);
        setLoaderState("ready");
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        setLoaderState(error instanceof Error && error.message.includes("NEXT_PUBLIC") ? "missing-key" : "failed");
      });

    return () => {
      cancelled = true;
      circlesRef.current.forEach((circle) => circle.setMap(null));
      circlesRef.current = [];
      kakaoRef.current = null;
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!mapContainerRef.current || !mapRef.current || !kakaoRef.current?.maps || loaderState !== "ready") {
      return;
    }

    const container = mapContainerRef.current;
    const map = mapRef.current;
    const recenter = () => {
      map.relayout?.();
      map.setCenter(new kakaoRef.current!.maps.LatLng(KOREA_CENTER.lat, KOREA_CENTER.lng));
    };
    const resizeObserver = new ResizeObserver(() => requestAnimationFrame(recenter));
    resizeObserver.observe(container);
    window.addEventListener("resize", recenter);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", recenter);
    };
  }, [loaderState]);

  useEffect(() => {
    if (!kakaoRef.current || !mapRef.current || loaderState !== "ready") {
      return;
    }

    circlesRef.current.forEach((circle) => circle.setMap(null));
    circlesRef.current = points.map((point) => {
      const color = getRiskColor(point.risk_score);
      const fillOpacity = Math.max(0.14, Math.min(0.48, 0.16 + point.confidence * 0.28));
      const circle = new kakaoRef.current!.maps.Circle({
        center: new kakaoRef.current!.maps.LatLng(point.lat, point.lon),
        radius: point.circle_radius_m,
        strokeWeight: point.review_required ? 3 : 1,
        strokeColor: point.review_required ? "#ffffff" : color,
        strokeOpacity: point.review_required ? 0.95 : 0.62,
        strokeStyle: point.review_required ? "shortdash" : "solid",
        fillColor: color,
        fillOpacity,
      });
      circle.setMap(mapRef.current);
      kakaoRef.current!.maps.event.addListener(circle, "click", () => {
        setSelectedPoint(point);
      });
      return circle;
    });

    return () => {
      circlesRef.current.forEach((circle) => circle.setMap(null));
      circlesRef.current = [];
    };
  }, [loaderState, points]);

  const mapUnavailable = loaderState === "missing-key" || loaderState === "failed";

  return (
    <div className="card panel-section forest-heatmap-card">
      <div className="card__header">
        <div>
          <div className="badge">산림 히트맵</div>
          <h3 className="card__title">대한민국 산림성 산불 위험도 레이어</h3>
          <p className="card__lead">
            산림성 이력(STORUNST_CD=1 또는 임상코드 존재)만 Circle overlay로 표시합니다. 색상은 위험도, 진하기는 판정 신뢰도를 의미합니다.
          </p>
        </div>
        <span className={`status-chip status-chip--${heatmapResult.status === "ready" ? "ready" : heatmapResult.status === "error" ? "error" : "loading"}`}>
          {heatmapResult.status === "ready" ? "지도 데이터 준비" : heatmapResult.status === "error" ? "데이터 오류" : "데이터 확인 중"}
        </span>
      </div>

      {heatmapResult.status === "ready" ? (
        <div className="forest-heatmap__summary">
          <span className="badge">산림성 레코드 {heatmapResult.heatmap.forest_records}건</span>
          <span className="badge">표시 셀 {points.length}개</span>
          <span className="badge">고위험 {highRiskCount}개</span>
          <span className="badge">검토필요 {reviewRequiredCount}개</span>
          <span className="badge">업데이트 {formatDateLabel(heatmapResult.heatmap.generated_at)}</span>
        </div>
      ) : (
        <div className={`state-banner state-banner--${heatmapResult.status === "error" ? "error" : "loading"}`}>
          {heatmapResult.message}
        </div>
      )}

      <div className="forest-heatmap__layout">
        <div className="forest-heatmap__mapWrap">
          <div ref={mapContainerRef} className="forest-heatmap__map" aria-label="산림성 산불 위험도 지도" />
          {loaderState !== "ready" ? (
            <div className="mapOverlay">
              {mapUnavailable ? "카카오 지도 키 또는 SDK 상태를 확인하세요." : "카카오 지도를 불러오는 중입니다."}
            </div>
          ) : null}
        </div>
        <aside className="forest-heatmap__legend">
          <div>
            <strong>색상 범례</strong>
            <div className="forest-heatmap__legendBar" />
            <div className="forest-heatmap__legendLabels">
              <span>낮음</span>
              <span>중간</span>
              <span>높음</span>
            </div>
          </div>
          <p>원 크기는 해당 산림 격자 주변의 누적 발생 수와 위험도에 따라 커집니다.</p>
          <p>흰색 점선 테두리는 위험도 대비 신뢰도가 낮아 에이전트 정밀 검토가 필요한 후보입니다.</p>
          {selectedPoint ? (
            <div className="forest-heatmap__selected">
              <span className="badge">선택 지점</span>
              <strong>{selectedPoint.province} {selectedPoint.city}</strong>
              <p>위험도 {getRiskLabel(selectedPoint.risk_level)} · {formatPercent(selectedPoint.risk_score)}</p>
              <p>신뢰도 {formatPercent(selectedPoint.confidence)} ± {formatPercent(selectedPoint.confidence_margin)}</p>
              <p>누적 {selectedPoint.incident_count}건 · 최근 {selectedPoint.latest_year ?? "-"}년 · 원인 {selectedPoint.top_cause ?? "미상"}</p>
              <a
                className="ghostLink monitoring-list__action"
                href={buildAnalyzeHref({
                  province: selectedPoint.province,
                  city: selectedPoint.city,
                  lat: selectedPoint.lat,
                  lon: selectedPoint.lon,
                  radiusKm: Math.max(3, Math.round(selectedPoint.circle_radius_m / 1000)),
                  autoRun: true,
                })}
              >
                이 지점 /analyze 자동 실행
              </a>
            </div>
          ) : (
            <div className="empty-list">지도 원을 클릭하면 위험도와 신뢰도 요약을 볼 수 있습니다.</div>
          )}
        </aside>
      </div>
    </div>
  );
}
