from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import random
from datetime import datetime, timedelta
import sys
from pathlib import Path

from backend.app.schemas.ai import AIReportRequest, AIReportResponse

# Add ai_engine to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import AI modules
from ai_engine.data_processor import DataProcessor, SensorReading
from ai_engine.predictor import Predictor
from ai_engine.optimizer import RouteOptimizer, BinLocation
from ai_engine.llm_wrapper import LLMWrapper

app = FastAPI()

# Approximate Almaty city bounds (urban core only).
ALMATY_CITY_BOUNDS = {
    "lat_min": 43.195,
    "lat_max": 43.305,
    "lng_min": 76.84,
    "lng_max": 76.985,
}


def _is_excluded_zone(lat: float, lng: float) -> bool:
    """Exclude mountain south-east and far peripheral edges from mock generation."""
    # South-east mountain belt (Medeu direction)
    if lat < 43.22 and lng > 76.955:
        return True

    # Far western periphery
    if lat < 43.215 and lng < 76.86:
        return True

    return False


def _generate_city_point() -> tuple[float, float]:
    """Generate a random point limited to urban Almaty bounds."""
    for _ in range(300):
        lat = random.uniform(ALMATY_CITY_BOUNDS["lat_min"], ALMATY_CITY_BOUNDS["lat_max"])
        lng = random.uniform(ALMATY_CITY_BOUNDS["lng_min"], ALMATY_CITY_BOUNDS["lng_max"])
        if not _is_excluded_zone(lat, lng):
            return lat, lng

    # Fallback to city center if random sampling failed repeatedly.
    return 43.2389, 76.9455

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Change this to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/bins")
def get_bins():
    items = []

    for i in range(50):
        lat, lng = _generate_city_point()
        items.append({
            "id": i,
            "lat": lat,
            "lng": lng,
            "fill_level": random.randint(0, 100)
        })

    return items


@app.post("/api/v1/ai/report", response_model=AIReportResponse)
def ai_report(request: AIReportRequest):
    """
    ПОЛНЫЙ ПАЙПЛАЙН AI:
    1. data_processor: валидация и обработка сырых данных
    2. predictor: расчёт скорости заполнения и прогноз времени переполнения
    3. optimizer: оптимизация маршрута для мусоровоза
    4. llm_wrapper: генерация текстового отчета (если Ollama доступна)
    """
    
    raw_readings = request.raw_readings
    start_point = request.start_point.model_dump()
    
    if not raw_readings:
        return {
            "predictions": [],
            "route": {
                "stops": [],
                "total_distance_km": 0,
                "estimated_duration_min": 0,
                "bins_count": 0,
                "truck_id": "TRUCK-01"
            },
            "report": {
                "what_is_happening": {
                    "ru": "Нет данных для анализа",
                    "en": "No data for analysis",
                    "kk": "Талдауға дерек жоқ"
                },
                "how_critical": {
                    "ru": "Низкий",
                    "en": "Low",
                    "kk": "Төмен"
                },
                "recommended_actions": {
                    "ru": "Отправьте данные с датчиков",
                    "en": "Send sensor data",
                    "kk": "Датчик деректерін жіберіңіз"
                }
            },
            "statistics": {
                "total_bins_analysed": 0,
                "critical_bins": 0,
                "warning_bins": 0,
                "normal_bins": 0,
                "average_fill_level": 0,
                "anomalies_detected": 0,
                "anomaly_reasons": []
            }
        }
    
    # ========== STEP 1: DATA PROCESSING ==========
    processor = DataProcessor(sensor_max_cm=100.0)
    
    # Обогатим данные историей (mock для демо)
    enriched_readings = []
    for r in raw_readings:
        # Mock история: 10 измерений за последний час
        timestamp = r.timestamp or datetime.utcnow()
        history_points = []
        current_fill = r.fill_level / 100 if r.fill_level > 1 else r.fill_level
        
        # Создаём 10 точек истории, растущих к текущему значению
        for i in range(10, 0, -1):
            prev_timestamp = timestamp - timedelta(minutes=i*5)  # каждые 5 минут
            # Симуляция: заполнение растёт примерно равномерно к текущему уровню
            prev_fill = max(0, current_fill - (i * 0.05))
            history_points.append({
                "timestamp": prev_timestamp.isoformat(),
                "fill_level": round(prev_fill, 4)
            })
        
        # Добавляем ТЕКУЩЕЕ значение в конец истории!
        history_points.append({
            "timestamp": timestamp.isoformat(),
            "fill_level": round(current_fill, 4)
        })
        
        enriched_readings.append({
            "bin_id": r.bin_id,
            "timestamp": timestamp.isoformat(),
            "fill_level": current_fill,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "district": r.district,
            "history": history_points
        })
    
    processed_bins = processor.process_readings(enriched_readings)
    
    # ========== STEP 2: PREDICTION ==========
    predictor = Predictor(window_size=10, min_readings=2)
    predictions = []
    anomalies = []
    critical_count = 0
    warning_count = 0
    normal_count = 0
    
    for pb in processed_bins:
        if pb.anomaly_detected:
            anomalies.append(pb.anomaly_reason)
        
        # Predict для каждого бака
        pred_result = predictor.predict(
            bin_id=pb.bin_id,
            history=pb.history,
            current_fill=pb.fill_level
        )
        
        predictions.append({
            "bin_id": pb.bin_id,
            "latitude": pb.latitude,
            "longitude": pb.longitude,
            "current_fill": round(pb.fill_level, 3),
            "status": pred_result.status.value,
            "fill_rate_per_hour": pred_result.fill_rate_per_hour,
            "minutes_until_full": pred_result.minutes_until_full,
            "predicted_full_at": pred_result.predicted_full_at,
            "confidence": pred_result.confidence
        })
        
        # Подсчёт для отчета
        if pred_result.status.value == "Critical":
            critical_count += 1
        elif pred_result.status.value == "Warning":
            warning_count += 1
        else:
            normal_count += 1
    
    # ========== STEP 3: ROUTE OPTIMIZATION ==========
    optimizer = RouteOptimizer(include_warning=True)
    
    # Преобразуем predictions в BinLocation для оптимайзера
    bin_locations = [
        BinLocation(
            bin_id=p["bin_id"],
            latitude=p["latitude"],
            longitude=p["longitude"],
            fill_level=p["current_fill"],
            status=p["status"],
            district="Central"
        )
        for p in predictions
    ]
    
    optimized_route = optimizer.optimize(
        bins=bin_locations,
        start_point=start_point,
        truck_id="TRUCK-01",
        max_stops=15
    )
    
    route_stops = []
    for stop in optimized_route.stops:
        route_stops.append({
            "order": stop.order,
            "bin_id": stop.bin_id,
            "latitude": stop.latitude,
            "longitude": stop.longitude,
            "district": stop.district,
            "distance_from_prev_km": round(stop.distance_from_prev_km, 2)
        })
    
    # ========== STEP 4: LLM REPORT GENERATION ==========
    llm = LLMWrapper()
    
    avg_fill = sum(p["current_fill"] for p in predictions) / len(predictions) if predictions else 0
    most_problematic = "Central"  # можно улучшить с real district data
    
    context = {
        "total_bins": len(predictions),
        "critical_bins": critical_count,
        "warning_bins": warning_count,
        "normal_bins": normal_count,
        "avg_fill_level": avg_fill,
        "most_problematic_district": most_problematic,
        "route_stops": len(route_stops),
        "route_distance_km": optimized_route.total_distance_km,
        "route_eta_min": optimized_route.estimated_duration_min,
        "anomalies": anomalies
    }
    
    try:
        situation_report = llm.generate_report(context)
    except Exception as e:
        # Ollama не доступна или таймаут — используем fallback
        situation_report = llm._fallback(f"LLM техническая проблема: {str(e)}")
    
    # ========== RETURN FULL RESPONSE ==========
    return {
        "predictions": predictions,
        "route": {
            "stops": route_stops,
            "total_distance_km": round(optimized_route.total_distance_km, 2),
            "estimated_duration_min": optimized_route.estimated_duration_min,
            "bins_count": len(route_stops),
            "truck_id": optimized_route.truck_id
        },
        "report": {
            "what_is_happening": situation_report.what_is_happening,
            "how_critical": situation_report.how_critical,
            "recommended_actions": situation_report.recommended_actions
        },
        "statistics": {
            "total_bins_analysed": len(predictions),
            "critical_bins": critical_count,
            "warning_bins": warning_count,
            "normal_bins": normal_count,
            "average_fill_level": round(avg_fill * 100, 1),
            "anomalies_detected": len(anomalies),
            "anomaly_reasons": anomalies
        }
    }
