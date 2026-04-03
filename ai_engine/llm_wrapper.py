"""
llm_wrapper.py
Генерирует текстовый отчёт через локальную модель Ollama (llama3.2:1b).
Ollama должен быть запущен: ollama serve
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict
from urllib import request as urlrequest
from urllib import error as urlerror

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:1b"


@dataclass
class SituationReport:
    what_is_happening: Dict[str, str]
    how_critical: Dict[str, str]
    recommended_actions: Dict[str, str]
    raw_response: str


class LLMWrapper:
    """
    Отправляет агрегированные данные в локальную Ollama
    и возвращает структурированный шаблонный отчёт на 3 языках.
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
            return self._rule_based_report(
                context,
                "Ollama не запущена или модель не загружена. "
                "Запусти: ollama serve; ollama pull llama3.2:1b"
            )

        prompt = self._build_prompt(context)
        raw = self._call_ollama(prompt)
        return self._parse_response(raw, context)

    def _build_prompt(self, ctx: dict) -> str:
        avg_pct = round(ctx.get("avg_fill_level", 0) * 100)
        anomalies = ctx.get("anomalies", [])
        anomaly_text = ", ".join(anomalies[:3]) if anomalies else "нет"

        return f"""Ты аналитик по вывозу мусора.
    Верни ТОЛЬКО валидный JSON по строгому шаблону и заполни его содержательно на основе данных.
    Ответ должен быть немного подробнее: 2-3 коротких предложения в what_is_happening и 3 шага в recommended_actions.

ДАННЫЕ:
- Всего баков: {ctx.get('total_bins', 0)}
- Критических (>85%): {ctx.get('critical_bins', 0)}
- Предупреждение (60-85%): {ctx.get('warning_bins', 0)}
- Нормальных (<60%): {ctx.get('normal_bins', 0)}
- Средний уровень заполнения: {avg_pct}%
- Самый проблемный район: {ctx.get('most_problematic_district', 'неизвестно')}
- Маршрут: {ctx.get('route_stops', 0)} остановок, {ctx.get('route_distance_km', 0)} км, ETA {ctx.get('route_eta_min', 0)} мин
- Аномалии: {anomaly_text}

ПРАВИЛА:
- how_critical должен зависеть от ситуации (критических баков и среднего заполнения).
- recommended_actions должны быть конкретными и операционными.
- Переводы ru/en/kk должны быть семантически эквивалентны.

Шаблон JSON:
{{
    "what_is_happening": {{
        "ru": "...",
        "en": "...",
        "kk": "..."
    }},
    "how_critical": {{
        "ru": "...",
        "en": "...",
        "kk": "..."
    }},
    "recommended_actions": {{
        "ru": "1) ...\\n2) ...\\n3) ...",
        "en": "1) ...\\n2) ...\\n3) ...",
        "kk": "1) ...\\n2) ...\\n3) ..."
    }}
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

    def _parse_response(self, raw: str, context: dict) -> SituationReport:
        if not raw:
            return self._rule_based_report(context, "Ollama вернула пустой ответ")

        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()

        try:
            parsed = json.loads(clean)
            if not self._is_valid_report_payload(parsed):
                return self._rule_based_report(context, "Ответ Ollama не соответствует шаблону")

            what = self._localized(parsed.get("what_is_happening"), self._default_localized("Данные анализируются"))
            critical = self._localized(parsed.get("how_critical"), self._default_localized("Неизвестно"))
            actions = self._localized(
                parsed.get("recommended_actions"),
                self._default_localized("1) Проверить данные\n2) Актуализировать маршрут\n3) Мониторить ситуацию")
            )
            return SituationReport(
                what_is_happening=what,
                how_critical=critical,
                recommended_actions=actions,
                raw_response=raw,
            )
        except json.JSONDecodeError:
            return self._rule_based_report(context, "Ответ Ollama не JSON")

    def _default_localized(self, ru: str, en: str | None = None, kk: str | None = None) -> Dict[str, str]:
        return {
            "ru": ru,
            "en": en or ru,
            "kk": kk or ru,
        }

    def _localized(self, value, default: Dict[str, str]) -> Dict[str, str]:
        if not isinstance(value, dict):
            return default
        return {
            "ru": self._fix_text_encoding(str(value.get("ru", default["ru"]))),
            "en": self._fix_text_encoding(str(value.get("en", default["en"]))),
            "kk": self._fix_text_encoding(str(value.get("kk", default["kk"]))),
        }

    def _is_valid_localized(self, value) -> bool:
        if not isinstance(value, dict):
            return False

        for lang in ("ru", "en", "kk"):
            v = value.get(lang)
            if not isinstance(v, str) or len(v.strip()) < 3:
                return False

        return True

    def _is_valid_report_payload(self, parsed) -> bool:
        if not isinstance(parsed, dict):
            return False

        return (
            self._is_valid_localized(parsed.get("what_is_happening"))
            and self._is_valid_localized(parsed.get("how_critical"))
            and self._is_valid_localized(parsed.get("recommended_actions"))
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

    def _rule_based_report(self, context: dict, reason: str = "") -> SituationReport:
        logger.warning("LLM недоступна, используем rule-based отчёт: %s", reason)
        total = context.get("total_bins", 0)
        critical = context.get("critical_bins", 0)
        warning = context.get("warning_bins", 0)
        normal = context.get("normal_bins", 0)
        avg_pct = round(context.get("avg_fill_level", 0) * 100)
        distance = round(context.get("route_distance_km", 0), 2)
        eta = context.get("route_eta_min", 0)
        stops = context.get("route_stops", 0)

        if critical >= 8 or avg_pct >= 85:
            sev_ru, sev_en, sev_kk = "Критический", "Critical", "Сыни"
        elif critical >= 3 or avg_pct >= 70:
            sev_ru, sev_en, sev_kk = "Высокий", "High", "Жоғары"
        elif warning >= 5 or avg_pct >= 55:
            sev_ru, sev_en, sev_kk = "Средний", "Medium", "Орташа"
        else:
            sev_ru, sev_en, sev_kk = "Низкий", "Low", "Төмен"

        return SituationReport(
            what_is_happening={
                "ru": f"Проанализировано баков: {total}. Критических: {critical}, предупреждение: {warning}, нормальных: {normal}. Средняя заполненность {avg_pct}%.",
                "en": f"Bins analyzed: {total}. Critical: {critical}, warning: {warning}, normal: {normal}. Average fill level is {avg_pct}%.",
                "kk": f"Талданған бак саны: {total}. Қауіпті: {critical}, ескерту: {warning}, қалыпты: {normal}. Орташа толу деңгейі {avg_pct}%.",
            },
            how_critical={
                "ru": sev_ru,
                "en": sev_en,
                "kk": sev_kk,
            },
            recommended_actions={
                "ru": f"1) Алдымен критические баки обслужить.\n2) Подтвердить маршрут: {stops} остановок, {distance} км, ETA {eta} мин.\n3) Перепроверить данные датчиков и повторить анализ.",
                "en": f"1) Service critical bins first.\n2) Confirm route: {stops} stops, {distance} km, ETA {eta} min.\n3) Recheck sensor data and rerun analysis.",
                "kk": f"1) Алдымен қауіпті бактарды босатыңыз.\n2) Маршрутты растаңыз: {stops} аялдама, {distance} км, ETA {eta} мин.\n3) Датчик деректерін қайта тексеріп, талдауды қайталаңыз.",
            },
            raw_response="",
        )
