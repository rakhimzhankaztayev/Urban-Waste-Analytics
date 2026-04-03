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

interface LocalizedText {
  ru: string;
  en: string;
  kk: string;
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
    what_is_happening: LocalizedText;
    how_critical: LocalizedText;
    recommended_actions: LocalizedText;
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

type Language = 'ru' | 'en' | 'kk';

const UI_TEXT: Record<Language, Record<string, string>> = {
  ru: {
    subtitle: 'Умное управление отходами - Алматы',
    urgency: 'Срочность',
    high: 'Высокая',
    medium: 'Средняя',
    low: 'Низкая',
    na: 'Н/Д',
    critical: 'Критические',
    warning: 'Предупреждение',
    normal: 'Норма',
    stops: 'Остановки',
    distance: 'Дистанция',
    eta: 'ETA',
    route: 'Маршрут',
    truck: 'Грузовик',
    avgFill: 'Среднее заполнение',
    lastUpdate: 'Последнее обновление',
    refreshing: 'обновление...',
    routeCalculating: 'рассчитывается...',
    waitingAi: 'ожидаем ИИ',
    aiSituation: 'ИИ-Анализ',
    aiLoading: 'Загрузка AI-анализа...',
    criticality: 'Критичность',
    recommendation: 'Рекомендация',
    waitingModel: 'ожидаем ответ модели',
    checkBackend: 'Проверьте backend/ollama и повторите.',
    aiSoon: 'данные скоро появятся.',
    topPriorityBins: 'Приоритетные баки',
    criticalBinsTable: 'Таблица критических баков',
    bin: 'Бак',
    fill: 'Заполн.',
    conf: 'Увер.',
    coords: 'Коорд.',
    noCritical: 'Сейчас нет критических баков',
    status: 'Статус',
    fillLabel: 'Заполнение',
    etaFull: 'До полного',
    confidence: 'Уверенность',
    openPanel: 'Открыть панель',
    hidePanel: 'Скрыть панель',
    aiUnavailable: 'AI-отчет недоступен',
    unknown: 'Неизвестно',
    lang: 'Язык',
  },
  en: {
    subtitle: 'Smart Waste Management - Almaty',
    urgency: 'Urgency',
    high: 'High',
    medium: 'Medium',
    low: 'Low',
    na: 'N/A',
    critical: 'Critical',
    warning: 'Warning',
    normal: 'Normal',
    stops: 'Stops',
    distance: 'Distance',
    eta: 'ETA',
    route: 'Route',
    truck: 'Truck',
    avgFill: 'Avg Fill',
    lastUpdate: 'Last update',
    refreshing: 'refreshing...',
    routeCalculating: 'calculating...',
    waitingAi: 'waiting for AI',
    aiSituation: 'AI Situation',
    aiLoading: 'Loading AI analysis...',
    criticality: 'Criticality',
    recommendation: 'Recommendation',
    waitingModel: 'waiting for model response',
    checkBackend: 'Check backend/ollama and retry.',
    aiSoon: 'data will appear soon.',
    topPriorityBins: 'Top Priority Bins',
    criticalBinsTable: 'Critical Bins Table',
    bin: 'Bin',
    fill: 'Fill',
    conf: 'Conf',
    coords: 'Coords',
    noCritical: 'No critical bins now',
    status: 'Status',
    fillLabel: 'Fill',
    etaFull: 'ETA full',
    confidence: 'Confidence',
    openPanel: 'Open panel',
    hidePanel: 'Hide panel',
    aiUnavailable: 'AI report unavailable',
    unknown: 'Unknown',
    lang: 'Language',
  },
  kk: {
    subtitle: 'Ақылды қалдықтарды басқару - Алматы',
    urgency: 'Шұғылдық',
    high: 'Жоғары',
    medium: 'Орташа',
    low: 'Төмен',
    na: 'Ж/Қ',
    critical: 'Қауіпті',
    warning: 'Ескерту',
    normal: 'Қалыпты',
    stops: 'Аялдама',
    distance: 'Қашықтық',
    eta: 'ETA',
    route: 'Маршрут',
    truck: 'Көлік',
    avgFill: 'Орташа толу',
    lastUpdate: 'Соңғы жаңарту',
    refreshing: 'жаңартылуда...',
    routeCalculating: 'есептелуде...',
    waitingAi: 'ИИ күтілуде',
    aiSituation: 'ИИ Талдауы',
    aiLoading: 'AI талдауы жүктелуде...',
    criticality: 'Критикалығы',
    recommendation: 'Ұсыныс',
    waitingModel: 'модель жауабын күту',
    checkBackend: 'backend/ollama тексеріп, қайта көріңіз.',
    aiSoon: 'мәліметтер жақында шығады.',
    topPriorityBins: 'Басым бактар',
    criticalBinsTable: 'Қауіпті бактар кестесі',
    bin: 'Бак',
    fill: 'Толу',
    conf: 'Сенім',
    coords: 'Коорд.',
    noCritical: 'Қазір қауіпті бактар жоқ',
    status: 'Күйі',
    fillLabel: 'Толуы',
    etaFull: 'Толуға дейін',
    confidence: 'Сенімділік',
    openPanel: 'Панельді ашу',
    hidePanel: 'Панельді жасыру',
    aiUnavailable: 'AI есеп қолжетімсіз',
    unknown: 'Белгісіз',
    lang: 'Тіл',
  },
};

export default function WasteMap() {
  const [bins, setBins] = useState<Bin[]>([]);
  const [aiData, setAiData] = useState<AIReportResponse | null>(null);
  const [panelError, setPanelError] = useState<string>('');
  const [selectedBin, setSelectedBin] = useState<DisplayMarker | null>(null);
  const [roadRouteGeoJson, setRoadRouteGeoJson] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [panelCollapsed, setPanelCollapsed] = useState<boolean>(false);
  const [language, setLanguage] = useState<Language>('ru');

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

  const getUrgencyTone = (level: 'high' | 'medium' | 'low') => {
    if (level === 'high') return 'danger';
    if (level === 'medium') return 'warning';
    return 'normal';
  };

  const t = UI_TEXT[language];

  const pickLocalized = (value?: LocalizedText, fallback = '') => {
    if (!value) return fallback;
    return value[language] || value.ru || value.en || value.kk || fallback;
  };

  const formatStatus = (status: string) => {
    if (status === 'Critical') return t.critical;
    if (status === 'Warning') return t.warning;
    if (status === 'Normal') return t.normal;
    return status;
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

  const urgencyLevel: 'high' | 'medium' | 'low' = displayedStats
    ? displayedStats.critical_bins > 5
      ? 'high'
      : displayedStats.critical_bins > 0
        ? 'medium'
        : 'low'
    : 'low';

  const urgencyLabel = urgencyLevel === 'high' ? t.high : urgencyLevel === 'medium' ? t.medium : t.low;

  return (
    <div className={`mission-root lang-${language}`}>
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
              title={`${bin.id}: ${bin.fillPercent}% | ${formatStatus(bin.status)}`}
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
              <div>{t.status}: {formatStatus(selectedBin.status)}</div>
              <div>{t.fillLabel}: {selectedBin.fillPercent}%</div>
              <div>
                {t.etaFull}: {selectedBin.minutesUntilFull !== null ? `${selectedBin.minutesUntilFull} min` : t.na}
              </div>
              <div>{t.confidence}: {(selectedBin.confidence * 100).toFixed(0)}%</div>
            </div>
          </Popup>
        )}
      </Map>

      <div className={`mission-panel ${panelCollapsed ? 'collapsed' : ''}`}>
        <button
          type="button"
          className="panel-toggle"
          onClick={() => setPanelCollapsed((v) => !v)}
          title={panelCollapsed ? t.openPanel : t.hidePanel}
        >
          {panelCollapsed ? '›' : '‹'}
        </button>

        {!panelCollapsed && (
          <>
            <>
              <div className="panel-header">
                <div>
                  <strong className="panel-title">Urban Waste Analytics</strong>
                  <div className="panel-subtitle">{t.subtitle}</div>
                </div>
                <div className="panel-controls">
                  <label className="language-label" htmlFor="language-select">{t.lang}</label>
                  <select
                    id="language-select"
                    className="language-select"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value as Language)}
                  >
                    <option value="ru">Русский</option>
                    <option value="kk">Қазақша</option>
                    <option value="en">English</option>
                  </select>
                  <span className={`urgency-badge ${getUrgencyTone(urgencyLevel)}`}>{t.urgency}: {urgencyLabel}</span>
                </div>
              </div>

              <div className="kpi-grid">
                <div className="kpi-card critical">
                  <div className="kpi-value">{displayedStats.critical_bins}</div>
                  <div className="kpi-label">{t.critical}</div>
                </div>
                <div className="kpi-card warning">
                  <div className="kpi-value">{displayedStats.warning_bins}</div>
                  <div className="kpi-label">{t.warning}</div>
                </div>
                <div className="kpi-card normal">
                  <div className="kpi-value">{displayedStats.normal_bins}</div>
                  <div className="kpi-label">{t.normal}</div>
                </div>
                <div className="kpi-card neutral">
                  <div className="kpi-value">{aiReady ? (aiData?.route.bins_count ?? '-') : '-'}</div>
                  <div className="kpi-label">{t.stops}</div>
                </div>
                <div className="kpi-card neutral">
                  <div className="kpi-value">{aiReady ? `${aiData?.route.total_distance_km ?? '-'} km` : '-'}</div>
                  <div className="kpi-label">{t.distance}</div>
                </div>
                <div className="kpi-card neutral">
                  <div className="kpi-value">{aiReady ? `${aiData?.route.estimated_duration_min ?? '-'} min` : '-'}</div>
                  <div className="kpi-label">{t.eta}</div>
                </div>
              </div>

              <div className="route-summary">
                {aiReady ? (
                  <>
                    <div><strong>{t.route}:</strong> {aiData?.route.total_distance_km ?? '-'} km, {aiData?.route.estimated_duration_min ?? '-'} min</div>
                    <div><strong>{t.truck}:</strong> {aiData?.route.truck_id ?? 'TRUCK-01'}</div>
                    <div><strong>{t.stops}:</strong> {aiData?.route.bins_count ?? '-'}</div>
                  </>
                ) : (
                  <>
                    <div><strong>{t.route}:</strong> {t.routeCalculating}</div>
                    <div><strong>{t.truck}:</strong> TRUCK-01</div>
                    <div><strong>{t.stops}:</strong> {t.waitingAi}</div>
                  </>
                )}
                <div><strong>{t.avgFill}:</strong> {displayedStats.average_fill_level}%</div>
                <div><strong>{t.lastUpdate}:</strong> {lastUpdated || t.na} {loading ? `(${t.refreshing})` : ''}</div>
              </div>

              <div className="report-block report-block-primary">
                <div className="block-title">{t.aiSituation}</div>
                {aiReady ? (
                  <>
                    <div style={{ marginBottom: 6 }}>{pickLocalized(aiData?.report.what_is_happening, t.aiUnavailable)}</div>
                    <div style={{ marginBottom: 6 }}><strong>{t.criticality}:</strong> {pickLocalized(aiData?.report.how_critical, t.unknown)}</div>
                    <div><strong>{t.recommendation}:</strong> {pickLocalized(aiData?.report.recommended_actions, t.checkBackend)}</div>
                  </>
                ) : loading ? (
                  <>
                    <div style={{ marginBottom: 6 }}>{t.aiLoading}</div>
                    <div style={{ marginBottom: 6 }}><strong>{t.criticality}:</strong> {t.routeCalculating}</div>
                    <div><strong>{t.recommendation}:</strong> {t.waitingModel}</div>
                  </>
                ) : panelError ? (
                  <>
                    <div style={{ marginBottom: 6 }}>{panelError}</div>
                    <div style={{ marginBottom: 6 }}><strong>{t.criticality}:</strong> {t.unknown}</div>
                    <div><strong>{t.recommendation}:</strong> {t.checkBackend}</div>
                  </>
                ) : (
                  <>
                    <div style={{ marginBottom: 6 }}>{t.waitingAi}</div>
                    <div style={{ marginBottom: 6 }}><strong>{t.criticality}:</strong> {t.routeCalculating}</div>
                    <div><strong>{t.recommendation}:</strong> {t.aiSoon}</div>
                  </>
                )}
              </div>

              <div className="block-title">{t.topPriorityBins}</div>
              <div className="priority-list">
                {topPriorityBins.map((bin) => (
                  <div key={`priority-${bin.id}`} className="priority-row">
                    <span>{bin.id}</span>
                    <span style={{ color: getColorByStatus(bin.status), fontWeight: 700 }}>{formatStatus(bin.status)}</span>
                    <span>{bin.fillPercent}%</span>
                    <span>{bin.minutesUntilFull !== null ? `${bin.minutesUntilFull} min` : t.na}</span>
                  </div>
                ))}
              </div>

              <div className="block-title" style={{ marginTop: 10 }}>{t.criticalBinsTable}</div>
              <div className="critical-table-wrap">
                <table className="critical-table">
                  <thead>
                    <tr>
                      <th>{t.bin}</th>
                      <th>{t.fill}</th>
                      <th>{t.eta}</th>
                      <th>{t.conf}</th>
                      <th>{t.coords}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {criticalBins.length === 0 && (
                      <tr>
                        <td colSpan={5} className="critical-empty">{t.noCritical}</td>
                      </tr>
                    )}
                    {criticalBins.slice(0, 20).map((bin) => (
                      <tr key={`critical-${bin.id}`}>
                        <td>{bin.id}</td>
                        <td>{bin.fillPercent}%</td>
                        <td>{bin.minutesUntilFull !== null ? `${bin.minutesUntilFull}m` : t.na}</td>
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
