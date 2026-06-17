"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Coordinates = {
  lat: number;
  lng: number;
};

type RadiusPoints = {
  north: { lat: number; lon: number };
  south: { lat: number; lon: number };
  east: { lat: number; lon: number };
  west: { lat: number; lon: number };
};

type HistoricalIncident = {
  id: string;
  title: string;
  lat: number;
  lng: number;
  occurredAt?: string;
  description?: string;
};

type MapPanelProps = {
  selectedCoordinates?: Coordinates | null;
  defaultCenter?: Coordinates;
  historicalIncidents?: HistoricalIncident[];
  analysisRadiusKm?: number | null;
  radiusPoints?: RadiusPoints | null;
  onCoordinateSelect?: (coordinates: Coordinates) => void;
};

type LoaderState = "idle" | "loading" | "ready" | "missing-key" | "failed";

const KAKAO_ERROR_HELP =
  "현재 Kakao Developers 앱에서 OPEN_MAP_AND_LOCAL(지도 JavaScript SDK) 서비스가 비활성화되어 있거나 허용 도메인이 맞지 않을 수 있습니다. Kakao Developers에서 JavaScript 키 사용 앱의 지도 서비스와 웹 플랫폼(예: http://localhost:3000, http://127.0.0.1:3000)을 확인하세요.";

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

const DEFAULT_CENTER: Coordinates = { lat: 37.110673, lng: 127.297152 };
const KAKAO_SCRIPT_ID = "kakao-maps-sdk";
const KAKAO_KEY = process.env.NEXT_PUBLIC_KAKAO_JAVASCRIPT_KEY;
let kakaoMapsLoaderPromise: Promise<NonNullable<Window["kakao"]>> | null = null;

function formatCoordinate(value: number) {
  return value.toFixed(6);
}

function formatDistance(value: number) {
  return `${value.toFixed(value >= 10 ? 0 : 1)}km`;
}

function createSelectedMarkerImage(kakao: NonNullable<Window["kakao"]>) {
  return new kakao.maps.MarkerImage(
    "data:image/svg+xml;charset=UTF-8," +
      encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="42" viewBox="0 0 32 42" fill="none"><path d="M16 1C8.268 1 2 7.268 2 15c0 10.5 14 26 14 26s14-15.5 14-26C30 7.268 23.732 1 16 1Z" fill="#FF6B2C" stroke="#FFE0D0" stroke-width="2"/><circle cx="16" cy="15" r="5" fill="#fff"/></svg>`,
      ),
    new kakao.maps.Size(32, 42),
    { offset: new kakao.maps.Point(16, 40) },
  );
}

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

export function MapPanel({
  selectedCoordinates,
  defaultCenter = DEFAULT_CENTER,
  historicalIncidents = [],
  analysisRadiusKm,
  radiusPoints,
  onCoordinateSelect,
}: MapPanelProps) {
  const initialCenter = selectedCoordinates ?? defaultCenter;
  const radiusMeters = typeof analysisRadiusKm === "number" && analysisRadiusKm > 0 ? analysisRadiusKm * 1000 : 0;
  const kakaoRef = useRef<NonNullable<Window["kakao"]> | null>(null);
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<KakaoMap | null>(null);
  const selectedMarkerRef = useRef<KakaoMarker | null>(null);
  const incidentMarkersRef = useRef<KakaoMarker[]>([]);
  const radiusCircleRef = useRef<KakaoCircle | null>(null);
  const onCoordinateSelectRef = useRef(onCoordinateSelect);
  const centerRef = useRef<Coordinates>(initialCenter);
  const radiusMetersRef = useRef(radiusMeters);
  const [loaderState, setLoaderState] = useState<LoaderState>(KAKAO_KEY ? "idle" : "missing-key");
  const [statusMessage, setStatusMessage] = useState(
    KAKAO_KEY
      ? "지도를 불러오는 중입니다."
      : "카카오 지도 키가 설정되지 않아 텍스트 기반 위치 선택 안내만 제공합니다.",
  );
  const [internalSelected, setInternalSelected] = useState<Coordinates | null>(selectedCoordinates ?? null);

  const resolvedSelected = selectedCoordinates ?? internalSelected;
  const resolvedCenter = resolvedSelected ?? defaultCenter;
  const resolvedCenterLat = resolvedCenter.lat;
  const resolvedCenterLng = resolvedCenter.lng;

  const incidentSummary = useMemo(() => {
    return historicalIncidents.map((incident) => ({
      ...incident,
      coordinateLabel: `${formatCoordinate(incident.lat)}, ${formatCoordinate(incident.lng)}`,
    }));
  }, [historicalIncidents]);

  useEffect(() => {
    setInternalSelected(selectedCoordinates ?? null);
  }, [selectedCoordinates]);

  useEffect(() => {
    onCoordinateSelectRef.current = onCoordinateSelect;
  }, [onCoordinateSelect]);

  useEffect(() => {
    centerRef.current = { lat: resolvedCenterLat, lng: resolvedCenterLng };
  }, [resolvedCenterLat, resolvedCenterLng]);

  useEffect(() => {
    radiusMetersRef.current = radiusMeters;
  }, [radiusMeters]);

  useEffect(() => {
    if (!KAKAO_KEY) {
      setLoaderState("missing-key");
      setStatusMessage("NEXT_PUBLIC_KAKAO_JAVASCRIPT_KEY가 없어 지도를 표시할 수 없습니다.");
      return;
    }

    let cancelled = false;
    setLoaderState("loading");
    setStatusMessage("카카오 지도를 불러오는 중입니다.");

    loadKakaoMapsScript()
      .then((kakao) => {
        if (cancelled || !mapContainerRef.current || mapRef.current) {
          return;
        }

        kakaoRef.current = kakao;
        const { lat, lng } = centerRef.current;
        const startCenter = new kakao.maps.LatLng(lat, lng);
        const map = new kakao.maps.Map(mapContainerRef.current, {
          center: startCenter,
          level: 6,
        });

        mapRef.current = map;
        const relayoutAndCenter = () => {
          map.relayout?.();
          map.setCenter(new kakao.maps.LatLng(centerRef.current.lat, centerRef.current.lng));
        };

        requestAnimationFrame(relayoutAndCenter);
        window.setTimeout(() => {
          if (!cancelled && mapRef.current === map) {
            relayoutAndCenter();
          }
        }, 120);

        const selectedMarkerImage = createSelectedMarkerImage(kakao);
        const selectedMarker = new kakao.maps.Marker({
          position: startCenter,
          image: selectedMarkerImage,
        });
        selectedMarker.setMap(map);
        selectedMarkerRef.current = selectedMarker;

        const radiusCircle = new kakao.maps.Circle({
          center: startCenter,
          radius: radiusMetersRef.current,
          strokeWeight: 2,
          strokeColor: "#57a4be",
          strokeOpacity: 0.75,
          strokeStyle: "solid",
          fillColor: "#57a4be",
          fillOpacity: 0.12,
        });
        radiusCircle.setMap(map);
        radiusCircleRef.current = radiusCircle;

        kakao.maps.event.addListener(map, "click", (mouseEvent) => {
          const nextCoordinates = {
            lat: mouseEvent.latLng.getLat(),
            lng: mouseEvent.latLng.getLng(),
          };

          setInternalSelected(nextCoordinates);
          selectedMarkerRef.current?.setPosition?.(new kakao.maps.LatLng(nextCoordinates.lat, nextCoordinates.lng));
          radiusCircleRef.current?.setPosition?.(new kakao.maps.LatLng(nextCoordinates.lat, nextCoordinates.lng));
          map.setCenter(new kakao.maps.LatLng(nextCoordinates.lat, nextCoordinates.lng));
          onCoordinateSelectRef.current?.(nextCoordinates);
        });

        setLoaderState("ready");
        setStatusMessage("지도를 클릭해 분석할 좌표를 선택하세요.");
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }

        const baseMessage = error instanceof Error ? error.message : "카카오 지도를 불러오지 못했습니다.";
        const helpMessage =
          baseMessage === "Kakao Maps SDK failed to load"
            ? `${baseMessage}. ${KAKAO_ERROR_HELP}`
            : baseMessage;

        setLoaderState("failed");
        setStatusMessage(helpMessage);
      });

    return () => {
      cancelled = true;
      selectedMarkerRef.current?.setMap(null);
      selectedMarkerRef.current = null;
      radiusCircleRef.current?.setMap(null);
      radiusCircleRef.current = null;
      incidentMarkersRef.current.forEach((marker) => marker.setMap(null));
      incidentMarkersRef.current = [];
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
      const position = new kakaoRef.current!.maps.LatLng(centerRef.current.lat, centerRef.current.lng);
      map.relayout?.();
      map.setCenter(position);
    };

    const resizeObserver = new ResizeObserver(() => {
      requestAnimationFrame(recenter);
    });

    resizeObserver.observe(container);
    window.addEventListener("resize", recenter);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", recenter);
    };
  }, [loaderState]);

  useEffect(() => {
    if (!kakaoRef.current || !mapRef.current) {
      return;
    }

    incidentMarkersRef.current.forEach((marker) => marker.setMap(null));
    incidentMarkersRef.current = historicalIncidents.map((incident) => {
      const marker = new kakaoRef.current!.maps.Marker({
        map: mapRef.current,
        position: new kakaoRef.current!.maps.LatLng(incident.lat, incident.lng),
        title: incident.title,
      });
      return marker;
    });

    return () => {
      incidentMarkersRef.current.forEach((marker) => marker.setMap(null));
      incidentMarkersRef.current = [];
    };
  }, [historicalIncidents]);

  useEffect(() => {
    if (!kakaoRef.current?.maps || !mapRef.current || !selectedMarkerRef.current || !resolvedSelected) {
      return;
    }

    const nextPosition = new kakaoRef.current.maps.LatLng(resolvedSelected.lat, resolvedSelected.lng);
    selectedMarkerRef.current.setPosition?.(nextPosition);
    radiusCircleRef.current?.setPosition?.(nextPosition);
    mapRef.current.setCenter(nextPosition);
  }, [resolvedSelected]);

  useEffect(() => {
    radiusCircleRef.current?.setRadius?.(radiusMeters);
  }, [radiusMeters]);

  const showMapCanvas = loaderState === "loading" || loaderState === "ready";
  const showFallback = loaderState === "missing-key" || loaderState === "failed";

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div>
        <div className="badge">Kakao Map</div>
        <h3 style={{ marginBottom: 8 }}>좌표 선택 및 반경 시각화</h3>
        <p style={{ margin: 0, color: "#b9cad1", lineHeight: 1.6 }}>{statusMessage}</p>
      </div>

      {showMapCanvas ? (
        <div className="mapWrapper" style={{ minHeight: 360 }}>
          <div
            ref={mapContainerRef}
            className="mapMock"
            style={{
              height: 360,
              overflow: "hidden",
            }}
          />
          {loaderState === "loading" ? <div className="mapOverlay">카카오 지도 로딩 중…</div> : null}
        </div>
      ) : null}

      {showFallback ? (
        <div
          className="card"
          style={{
            borderStyle: "dashed",
            background: "rgba(16, 35, 44, 0.65)",
          }}
        >
          <strong style={{ display: "block", marginBottom: 8 }}>지도 미리보기를 사용할 수 없습니다.</strong>
          <p style={{ margin: 0, color: "#b9cad1", lineHeight: 1.6 }}>
            환경 변수 <code>NEXT_PUBLIC_KAKAO_JAVASCRIPT_KEY</code>를 설정하면 클릭 기반 좌표 선택, 반경 원형
            시각화, 과거 산불 마커 표시를 활성화할 수 있습니다.
          </p>
        </div>
      ) : null}

      <div className="card mapSummaryCard" style={{ display: "grid", gap: 12 }}>
        <div>
          <div className="badge">선택 좌표</div>
          <p style={{ margin: "12px 0 0", color: "#d9e5ea" }}>
            위도 {formatCoordinate(resolvedCenter.lat)} / 경도 {formatCoordinate(resolvedCenter.lng)}
          </p>
          <p style={{ margin: "8px 0 0", color: "#8db0bb", fontSize: "0.95rem" }}>
            지도에서 클릭하면 선택 좌표가 갱신되고 상위 컴포넌트에 즉시 전달됩니다.
          </p>
        </div>

        <div>
          <div className="badge">선택 반경</div>
          <p style={{ margin: "12px 0 0", color: "#d9e5ea" }}>
            {radiusMeters > 0 ? `${formatDistance(radiusMeters / 1000)} 반경을 기준으로 주변 맥락을 조회합니다.` : "반경 정보가 아직 없습니다."}
          </p>
          {radiusPoints ? (
            <div className="mapBoundsGrid">
              <div>
                <span>북쪽</span>
                <strong>{formatCoordinate(radiusPoints.north.lat)}, {formatCoordinate(radiusPoints.north.lon)}</strong>
              </div>
              <div>
                <span>남쪽</span>
                <strong>{formatCoordinate(radiusPoints.south.lat)}, {formatCoordinate(radiusPoints.south.lon)}</strong>
              </div>
              <div>
                <span>동쪽</span>
                <strong>{formatCoordinate(radiusPoints.east.lat)}, {formatCoordinate(radiusPoints.east.lon)}</strong>
              </div>
              <div>
                <span>서쪽</span>
                <strong>{formatCoordinate(radiusPoints.west.lat)}, {formatCoordinate(radiusPoints.west.lon)}</strong>
              </div>
            </div>
          ) : null}
        </div>

        <div>
          <div className="badge">과거 산불 이력</div>
          {incidentSummary.length > 0 ? (
            <ul className="list" style={{ marginTop: 12 }}>
              {incidentSummary.map((incident) => (
                <li key={incident.id} style={{ marginBottom: 10 }}>
                  <strong>{incident.title}</strong>
                  <div style={{ color: "#8db0bb", fontSize: "0.95rem" }}>{incident.coordinateLabel}</div>
                  {incident.occurredAt ? (
                    <div style={{ color: "#8db0bb", fontSize: "0.95rem" }}>{incident.occurredAt}</div>
                  ) : null}
                  {incident.description ? <div style={{ color: "#d9e5ea" }}>{incident.description}</div> : null}
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ margin: "12px 0 0", color: "#8db0bb" }}>
              제공된 과거 산불 이력이 없어서 지도 마커와 목록을 표시하지 않습니다.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
