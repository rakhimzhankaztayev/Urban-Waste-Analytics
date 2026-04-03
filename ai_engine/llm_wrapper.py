"""
llm_wrapper.py
Генерирует текстовый отчёт через локальную модель Ollama (llama3.2:1b).
Ollama должен быть запущен: ollama serve
"""

import json
import logging
from dataclasses import dataclass
from urllib import request as urlrequest
from urllib import error as urlerror

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:1b"


@dataclass
class SituationReport:
    what_is_happening: str
    how_critical: str
    recommended_actions: str
    raw_response: str


class LLMWrapper:
    """
    Отправляет агрегированные данные в локальную Ollama
    и возвращает структурированный отчёт на русском языке.
    """

    def __init__(self, model: str = MODEL, ollama_url: str = OLLAMA_URL):
        self.model = model
        self.ollama_url = ollama_url

    def health_check(self) -> bool:
        """Проверяет что Ollama запущена и модель доступна."""
        try:
            with urlrequest.urlopen("http://localhost:11434/api/tags", timeout=3) as response:
                payload = response.read().decode("utf-8")
            data = json.loads(payload)
            models = [m["name"] for m in data.get("models", [])]
            return any(self.model in m for m in models)
        except Exception:
            return False

    def generate_report(self, context: dict) -> SituationReport:
        if not self.health_check():
            return self._fallback(
                "Ollama не запущена или модель не загружена. "
                "Запусти: ollama serve; ollama pull llama3.2:1b"
            )

        prompt = self._build_prompt(context)
        raw = self._call_ollama(prompt)
        return self._parse_response(raw)

    def _build_prompt(self, ctx: dict) -> str:
        avg_pct = round(ctx.get("avg_fill_level", 0) * 100)
        anomalies = ctx.get("anomalies", [])
        anomaly_text = ", ".join(anomalies[:3]) if anomalies else "нет"

        return f"""Ты аналитик по вывозу мусора. Верни КРАТКИЙ JSON на русском.

ДАННЫЕ:
- Всего баков: {ctx.get('total_bins', 0)}
- Критических (>85%): {ctx.get('critical_bins', 0)}
- Предупреждение (60-85%): {ctx.get('warning_bins', 0)}
- Нормальных (<60%): {ctx.get('normal_bins', 0)}
- Средний уровень заполнения: {avg_pct}%
- Самый проблемный район: {ctx.get('most_problematic_district', 'неизвестно')}
- Маршрут: {ctx.get('route_stops', 0)} остановок, {ctx.get('route_distance_km', 0)} км, ETA {ctx.get('route_eta_min', 0)} мин
- Аномалии: {anomaly_text}

Ответь ТОЛЬКО валидным JSON (без markdown):
{{
    "what_is_happening": "коротко, до 20 слов",
    "how_critical": "Низкий/Средний/Высокий/Критический",
    "recommended_actions": "до 2 коротких действий"
}}"""

    def _call_ollama(self, prompt: str) -> str:
        try:
            payload = json.dumps(
                {
                    "model": self.model,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "num_predict": 96,
                    },
                }
            ).encode("utf-8")

            req = urlrequest.Request(
                self.ollama_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlrequest.urlopen(req, timeout=45) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data.get("response", "")
        except urlerror.URLError as e:
            logger.error("Ошибка сети при вызове Ollama: %s", e)
            return ""
        except Exception as e:
            logger.error("Ошибка вызова Ollama: %s", e)
            return ""

    def _parse_response(self, raw: str) -> SituationReport:
        if not raw:
            return self._fallback("Ollama вернула пустой ответ")

        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()

        try:
            parsed = json.loads(clean)
            what = self._fix_text_encoding(parsed.get("what_is_happening", ""))
            critical = self._fix_text_encoding(parsed.get("how_critical", ""))
            actions = self._fix_text_encoding(parsed.get("recommended_actions", ""))
            return SituationReport(
                what_is_happening=what,
                how_critical=critical,
                recommended_actions=actions,
                raw_response=raw,
            )
        except json.JSONDecodeError:
            return SituationReport(
                what_is_happening=self._fix_text_encoding(raw[:300]),
                how_critical="Не определён",
                recommended_actions="Проверьте лог системы",
                raw_response=raw,
            )

    def _fix_text_encoding(self, text: str) -> str:
        """Best-effort recovery for mojibake like 'Ð¢ÐµÐºÑ...' in Cyrillic output."""
        if not text:
            return text

        if "Ð" not in text and "Ñ" not in text:
            return text

        try:
            return text.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
        except Exception:
            return text

    def _fallback(self, reason: str) -> SituationReport:
        logger.warning("LLM недоступна: %s", reason)
        return SituationReport(
            what_is_happening=f"AI-отчёт недоступен: {reason}",
            how_critical="Неизвестно",
            recommended_actions="Проверьте статус Ollama и повторите запрос.",
            raw_response="",
        )
