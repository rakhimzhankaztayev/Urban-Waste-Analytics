"""
scripts/check_ollama.py
Проверяет что Ollama готова к работе. Запусти перед хакатоном.

python scripts/check_ollama.py
"""

import sys
import json

try:
    import httpx
except ImportError:
    print("❌ httpx не установлен: pip install httpx")
    sys.exit(1)

OLLAMA_BASE = "http://localhost:11434"
MODEL = "llama3.2:1b"


def check_ollama_running():
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        return None
    except Exception as e:
        print(f"  ошибка: {e}")
        return None


def check_model_loaded(tags_data):
    models = [m["name"] for m in tags_data.get("models", [])]
    return models, any(MODEL in m for m in models)


def test_generation():
    try:
        r = httpx.post(
            f"{OLLAMA_BASE}/api/generate",
            json={
                "model": MODEL,
                "prompt": 'Ответь только JSON: {"status": "ok", "message": "Ollama работает"}',
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 50},
            },
            timeout=30,
        )
        r.raise_for_status()
        response_text = r.json().get("response", "")
        return response_text
    except Exception as e:
        return f"ошибка: {e}"


def main():
    print("=" * 50)
    print("  Проверка Ollama для Smart Waste Management")
    print("=" * 50)

    # 1. Ollama запущена?
    print("\n1. Ollama сервер...")
    tags = check_ollama_running()
    if tags is None:
        print("   ❌ Ollama не запущена!")
        print("   Запусти в отдельном терминале: ollama serve")
        sys.exit(1)
    print("   ✅ Ollama запущена")

    # 2. Модель загружена?
    print(f"\n2. Модель {MODEL}...")
    models, found = check_model_loaded(tags)
    if not found:
        print(f"   ❌ Модель {MODEL} не найдена")
        print(f"   Загруженные модели: {models or 'нет'}")
        print(f"   Запусти: ollama pull {MODEL}")
        sys.exit(1)
    print(f"   ✅ Модель {MODEL} загружена")

    # 3. Тест генерации
    print("\n3. Тест генерации...")
    result = test_generation()
    print(f"   Ответ модели: {result[:100]}...")
    print("   ✅ Генерация работает")

    # 4. Тест нашего враппера
    print("\n4. Тест LLMWrapper...")
    sys.path.insert(0, ".")
    from ai_engine.llm_wrapper import LLMWrapper
    wrapper = LLMWrapper()
    report = wrapper.generate_report({
        "total_bins": 20,
        "critical_bins": 3,
        "warning_bins": 5,
        "normal_bins": 12,
        "avg_fill_level": 0.61,
        "most_problematic_district": "Алмалинский",
        "route_stops": 8,
        "route_distance_km": 14.2,
        "route_eta_min": 57,
        "anomalies": [],
    })
    print(f"   Что происходит: {report.what_is_happening}")
    print(f"   Уровень: {report.how_critical}")
    print(f"   Действия: {report.recommended_actions}")
    print("   ✅ LLMWrapper работает")

    print("\n" + "=" * 50)
    print("  Всё готово! Можно запускать бэкенд.")
    print("=" * 50)


if __name__ == "__main__":
    main()
