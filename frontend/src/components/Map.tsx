import React, { useMemo, useState, useEffect } from 'react';
import Map, { Layer, Marker, Popup, Source } from 'react-map-gl';
// @ts-ignore
import 'mapbox-gl/dist/mapbox-gl.css';
import './Map.css';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || '';

interface Bin {
  id: number;
  lat: number;
  lng: number;
  fill_level: number;
}

interface Prediction {
  bin_id: string;
  latitude: number;
  longitude: number;
  current_fill: number;
  status: 'Critical' | 'Warning' | 'Normal' | string;
  fill_rate_per_hour: number;
  minutes_until_full: number | null;
  predicted_full_at: string | null;
  confidence: number;
}

interface RouteStop {
  order: number;
  bin_id: string;
  latitude: number;
  longitude: number;
  district: string;
  distance_from_prev_km: number;
}

interface AIReportResponse {
  predictions: Prediction[];
  route: {
    stops: RouteStop[];
    total_distance_km: number;
    estimated_duration_min: number;
    bins_count: number;
    truck_id: string;
  };
  report: {
    what_is_happening: string;
    how_critical: string;
    recommended_actions: string;
  };
  statistics: {
    total_bins_analysed: number;
    critical_bins: number;
    warning_bins: number;
    normal_bins: number;
    average_fill_level: number;
    anomalies_detected: number;
    anomaly_reasons: string[];
  };
}

interface DisplayMarker {
  id: string;
  lat: number;
  lng: number;
  fillPercent: number;
  status: string;
  minutesUntilFull: number | null;
  confidence: number;
}

export default function WasteMap() {
  const [bins, setBins] = useState<Bin[]>([]);
  const [aiData, setAiData] = useState<AIReportResponse | null>(null);
  const [panelError, setPanelError] = useState<string>('');
  const [selectedBin, setSelectedBin] = useState<DisplayMarker | null>(null);
  const [roadRouteGeoJson, setRoadRouteGeoJson] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [panelCollapsed, setPanelCollapsed] = useState<boolean>(false);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setPanelError('');
        const binsResponse = await fetch('http://localhost:8000/bins');
        const binsData: Bin[] = await binsResponse.json();
        setBins(binsData);

        const rawReadings = binsData.map((b, idx) => ({
          bin_id: `BIN-${String(idx + 1).padStart(3, '0')}`,
          latitude: b.lat,
          longitude: b.lng,
          fill_level: b.fill_level,
          district: 'Almaty-Central',
        }));

        const aiResponse = await fetch('http://localhost:8000/api/v1/ai/report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            raw_readings: rawReadings,
            start_point: { latitude: 43.2389, longitude: 76.9455 },
          }),
        });

        const aiJson: AIReportResponse = await aiResponse.json();
        setAiData(aiJson);
        setLastUpdated(new Date().toLocaleTimeString());
      } catch (err) {
        console.error('Error loading map data:', err);
        setPanelError('Не удалось загрузить данные AI. Проверьте backend и повторите.');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  const markers: DisplayMarker[] = useMemo(() => {
    if (aiData?.predictions?.length) {
      return aiData.predictions.map((p) => ({
        id: p.bin_id,
        lat: p.latitude,
        lng: p.longitude,
        fillPercent: Math.round(p.current_fill * 100),
        status: p.status,
        minutesUntilFull: p.minutes_until_full,
        confidence: p.confidence,
      }));
    }

    return bins.map((b) => ({
      id: `BIN-${b.id}`,
      lat: b.lat,
      lng: b.lng,
      fillPercent: b.fill_level,
      status: b.fill_level >= 85 ? 'Critical' : b.fill_level >= 60 ? 'Warning' : 'Normal',
      minutesUntilFull: null,
      confidence: 0,
    }));
  }, [aiData, bins]);

  const routeGeoJson = useMemo(() => {
    const stops = aiData?.route?.stops ?? [];
    if (stops.length < 2) {
      return null;
    }

    return {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: stops.map((s) => [s.longitude, s.latitude]),
          },
          properties: {},
        },
      ],
    };
  }, [aiData]);

  useEffect(() => {
    const stops = aiData?.route?.stops ?? [];
    if (stops.length < 2 || !MAPBOX_TOKEN) {
      setRoadRouteGeoJson(null);
      return;
    }

    const controller = new AbortController();

    const loadRoadRoute = async () => {
      try {
        const coords = stops.map((s) => `${s.longitude},${s.latitude}`).join(';');
        const url = `https://api.mapbox.com/directions/v5/mapbox/driving/${coords}?geometries=geojson&overview=full&steps=false&access_token=${MAPBOX_TOKEN}`;

        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`Directions API error: ${response.status}`);
        }

        const data = await response.json();
        const geometry = data?.routes?.[0]?.geometry;

        if (!geometry?.coordinates?.length) {
          throw new Error('No route geometry returned');
        }

        setRoadRouteGeoJson({
          type: 'FeatureCollection',
          features: [
            {
              type: 'Feature',
              geometry,
              properties: { source: 'mapbox-directions' },
            },
          ],
        });
      } catch (error) {
        console.warn('Falling back to straight route line:', error);
        setRoadRouteGeoJson(null);
      }
    };

    loadRoadRoute();

    return () => controller.abort();
  }, [aiData]);

  const getColorByStatus = (status: string) => {
    if (status === 'Critical') return '#cf2f2f';
    if (status === 'Warning') return '#e9961f';
    return '#1f8a52';
  };

  const getUrgencyTone = (label: string) => {
    if (label === 'High') return 'danger';
    if (label === 'Medium') return 'warning';
    return 'normal';
  };

  const topPriorityBins = useMemo(() => {
    return [...markers]
      .sort((a, b) => {
        const rank = (s: string) => (s === 'Critical' ? 0 : s === 'Warning' ? 1 : 2);
        const rankDiff = rank(a.status) - rank(b.status);
        if (rankDiff !== 0) return rankDiff;
        const aEta = a.minutesUntilFull ?? Number.MAX_SAFE_INTEGER;
        const bEta = b.minutesUntilFull ?? Number.MAX_SAFE_INTEGER;
        return aEta - bEta;
      })
      .slice(0, 5);
  }, [markers]);

  const criticalBins = useMemo(() => {
    return markers
      .filter((m) => m.status === 'Critical')
      .sort((a, b) => {
        if (b.fillPercent !== a.fillPercent) return b.fillPercent - a.fillPercent;
        const aEta = a.minutesUntilFull ?? Number.MAX_SAFE_INTEGER;
        const bEta = b.minutesUntilFull ?? Number.MAX_SAFE_INTEGER;
        return aEta - bEta;
      });
  }, [markers]);

  const fallbackStats = useMemo(() => {
    const critical = bins.filter((b) => b.fill_level >= 85).length;
    const warning = bins.filter((b) => b.fill_level >= 60 && b.fill_level < 85).length;
    const normal = bins.length - critical - warning;
    const avg = bins.length ? bins.reduce((sum, b) => sum + b.fill_level, 0) / bins.length : 0;

    return {
      total_bins_analysed: bins.length,
      critical_bins: critical,
      warning_bins: warning,
      normal_bins: normal,
      average_fill_level: Math.round(avg * 10) / 10,
      anomalies_detected: 0,
      anomaly_reasons: [],
    };
  }, [bins]);

  const displayedStats = aiData?.statistics ?? fallbackStats;
  const aiReady = Boolean(aiData);

  const urgencyLabel = displayedStats
    ? displayedStats.critical_bins > 5
      ? 'High'
      : displayedStats.critical_bins > 0
        ? 'Medium'
        : 'Low'
    : 'N/A';

  return (
    <div className="mission-root">
      <Map
        initialViewState={{
          longitude: 76.9455,
          latitude: 43.2389,
          zoom: 11.15,
        }}
        style={{ width: '100vw', height: '100vh' }}
        mapStyle="mapbox://styles/mapbox/navigation-day-v1"
        mapboxAccessToken={MAPBOX_TOKEN}
      >
        {(roadRouteGeoJson || routeGeoJson) && (
          <Source id="ai-route" type="geojson" data={(roadRouteGeoJson || routeGeoJson) as any}>
            <Layer
              id="ai-route-line"
              type="line"
              paint={{
                'line-color': '#2c7fb8',
                'line-width': 4,
                'line-opacity': 0.88,
              }}
            />
          </Source>
        )}

        {markers.map((bin) => (
          <Marker key={bin.id} longitude={bin.lng} latitude={bin.lat} anchor="bottom">
            <button
              className="bin-marker"
              type="button"
              style={{
                backgroundColor: getColorByStatus(bin.status),
                boxShadow: `0 0 0 4px ${getColorByStatus(bin.status)}22`,
              }}
              onClick={() => setSelectedBin(bin)}
              title={`${bin.id}: ${bin.fillPercent}% | ${bin.status}`}
            />
          </Marker>
        ))}

        {selectedBin && (
          <Popup
            longitude={selectedBin.lng}
            latitude={selectedBin.lat}
            closeOnClick={false}
            onClose={() => setSelectedBin(null)}
          >
            <div className="popup-content">
              <strong>{selectedBin.id}</strong>
              <div>Status: {selectedBin.status}</div>
              <div>Fill: {selectedBin.fillPercent}%</div>
              <div>
                ETA full: {selectedBin.minutesUntilFull !== null ? `${selectedBin.minutesUntilFull} min` : 'N/A'}
              </div>
              <div>Confidence: {(selectedBin.confidence * 100).toFixed(0)}%</div>
            </div>
          </Popup>
        )}
      </Map>

      <div className={`mission-panel ${panelCollapsed ? 'collapsed' : ''}`}>
        <button
          type="button"
          className="panel-toggle"
          onClick={() => setPanelCollapsed((v) => !v)}
          title={panelCollapsed ? 'Open panel' : 'Hide panel'}
        >
          {panelCollapsed ? '›' : '‹'}
        </button>

        {!panelCollapsed && (
          <>
            <>
              <div className="panel-header">
                <div>
                  <strong className="panel-title">Urban Waste Analytics</strong>
                  <div className="panel-subtitle">Smart Waste Management - Almaty</div>
                </div>
                <span className={`urgency-badge ${getUrgencyTone(urgencyLabel)}`}>Urgency: {urgencyLabel}</span>
              </div>

              <div className="kpi-grid">
                <div className="kpi-card critical">
                  <div className="kpi-value">{displayedStats.critical_bins}</div>
                  <div className="kpi-label">Critical</div>
                </div>
                <div className="kpi-card warning">
                  <div className="kpi-value">{displayedStats.warning_bins}</div>
                  <div className="kpi-label">Warning</div>
                </div>
                <div className="kpi-card normal">
                  <div className="kpi-value">{displayedStats.normal_bins}</div>
                  <div className="kpi-label">Normal</div>
                </div>
                <div className="kpi-card neutral">
                  <div className="kpi-value">{aiReady ? (aiData?.route.bins_count ?? '-') : '-'}</div>
                  <div className="kpi-label">Stops</div>
                </div>
                <div className="kpi-card neutral">
                  <div className="kpi-value">{aiReady ? `${aiData?.route.total_distance_km ?? '-'} km` : '-'}</div>
                  <div className="kpi-label">Distance</div>
                </div>
                <div className="kpi-card neutral">
                  <div className="kpi-value">{aiReady ? `${aiData?.route.estimated_duration_min ?? '-'} min` : '-'}</div>
                  <div className="kpi-label">ETA</div>
                </div>
              </div>

              <div className="route-summary">
                {aiReady ? (
                  <>
                    <div><strong>Route:</strong> {aiData?.route.total_distance_km ?? '-'} km, {aiData?.route.estimated_duration_min ?? '-'} min</div>
                    <div><strong>Truck:</strong> {aiData?.route.truck_id ?? 'TRUCK-01'}</div>
                    <div><strong>Stops:</strong> {aiData?.route.bins_count ?? '-'}</div>
                  </>
                ) : (
                  <>
                    <div><strong>Route:</strong> рассчитывается...</div>
                    <div><strong>Truck:</strong> TRUCK-01</div>
                    <div><strong>Stops:</strong> ожидаем AI</div>
                  </>
                )}
                <div><strong>Avg Fill:</strong> {displayedStats.average_fill_level}%</div>
                <div><strong>Last update:</strong> {lastUpdated || 'N/A'} {loading ? '(refreshing...)' : ''}</div>
              </div>

              <div className="report-block report-block-primary">
                <div className="block-title">AI Situation</div>
                {aiReady ? (
                  <>
                    <div style={{ marginBottom: 6 }}>{aiData?.report.what_is_happening ?? 'AI-отчет недоступен'}</div>
                    <div style={{ marginBottom: 6 }}><strong>Criticality:</strong> {aiData?.report.how_critical ?? 'Неизвестно'}</div>
                    <div><strong>Recommendation:</strong> {aiData?.report.recommended_actions ?? 'Проверьте backend/ollama и повторите.'}</div>
                  </>
                ) : loading ? (
                  <>
                    <div style={{ marginBottom: 6 }}>Загрузка AI-анализа...</div>
                    <div style={{ marginBottom: 6 }}><strong>Criticality:</strong> рассчитывается</div>
                    <div><strong>Recommendation:</strong> ожидаем ответ модели</div>
                  </>
                ) : panelError ? (
                  <>
                    <div style={{ marginBottom: 6 }}>{panelError}</div>
                    <div style={{ marginBottom: 6 }}><strong>Criticality:</strong> Неизвестно</div>
                    <div><strong>Recommendation:</strong> Проверьте backend/ollama и повторите.</div>
                  </>
                ) : (
                  <>
                    <div style={{ marginBottom: 6 }}>Ожидаем AI-аналитику...</div>
                    <div style={{ marginBottom: 6 }}><strong>Criticality:</strong> рассчитывается</div>
                    <div><strong>Recommendation:</strong> данные скоро появятся.</div>
                  </>
                )}
              </div>

              <div className="block-title">Top Priority Bins</div>
              <div className="priority-list">
                {topPriorityBins.map((bin) => (
                  <div key={`priority-${bin.id}`} className="priority-row">
                    <span>{bin.id}</span>
                    <span style={{ color: getColorByStatus(bin.status), fontWeight: 700 }}>{bin.status}</span>
                    <span>{bin.fillPercent}%</span>
                    <span>{bin.minutesUntilFull !== null ? `${bin.minutesUntilFull} min` : 'N/A'}</span>
                  </div>
                ))}
              </div>

              <div className="block-title" style={{ marginTop: 10 }}>Critical Bins Table</div>
              <div className="critical-table-wrap">
                <table className="critical-table">
                  <thead>
                    <tr>
                      <th>Bin</th>
                      <th>Fill</th>
                      <th>ETA</th>
                      <th>Conf</th>
                      <th>Coords</th>
                    </tr>
                  </thead>
                  <tbody>
                    {criticalBins.length === 0 && (
                      <tr>
                        <td colSpan={5} className="critical-empty">No critical bins now</td>
                      </tr>
                    )}
                    {criticalBins.slice(0, 20).map((bin) => (
                      <tr key={`critical-${bin.id}`}>
                        <td>{bin.id}</td>
                        <td>{bin.fillPercent}%</td>
                        <td>{bin.minutesUntilFull !== null ? `${bin.minutesUntilFull}m` : 'N/A'}</td>
                        <td>{(bin.confidence * 100).toFixed(0)}%</td>
                        <td>{bin.lat.toFixed(3)}, {bin.lng.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          </>
        )}
      </div>
    </div>
  );
}
