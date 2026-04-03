# 🗑️ Urban-Waste-Analytics: Smart City Waste Management
> **Прототип интеллектуальной системы управления городскими отходами на базе ИИ.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React-61DAFB.svg)](https://reactjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

---

## 📌 Проблема
Традиционные службы вывоза мусора работают по статичным графикам. Это приводит к двум крайностям:
1. **Переполнение:** Баки в людных местах переполняются быстрее, создавая антисанитарию.
2. **Неэффективность:** Мусоровозы заезжают во дворы с пустыми баками, впустую сжигая топливо и создавая пробки.

## 💡 Наше решение
**UrbanPulse** — это аналитическая панель (Dashboard), которая превращает хаотичный сбор мусора в точный, прогнозируемый процесс. 

### Ключевые возможности:
* 🔮 **Predictive Analytics:** ИИ предсказывает время заполнения бака на основе динамики накопления, а не просто констатирует факт переполнения.
* 🗺️ **Dynamic Routing:** Автоматическое построение кратчайшего маршрута только через «проблемные» точки (задача VRP).
* 🤖 **AI Management Insights:** Генерация управленческих рекомендаций на человеческом языке через LLM.
* 🌱 **Eco-Impact:** Мониторинг сокращения углеродного следа за счет оптимизации логистики.

---

## 🛠 Технологический стек

| Слой | Технологии |
| :--- | :--- |
| **Frontend** | React, Tailwind CSS, Mapbox GL JS |
| **Backend** | FastAPI (Python), PostgreSQL, Redis |
| **AI / Machine Learning** | Scikit-learn, NumPy, Google OR-Tools |
| **LLM** | OpenAI GPT-4o API |
| **DevOps** | Docker, Git |

---

## 🧠 Архитектура AI-Engine

Модуль ИИ является «мозгом» системы и разделен на три независимых компонента:

1.  **Predictor (`ai_engine/predictor.py`):** Использует анализ временных рядов для расчета скорости заполнения бака. Вычисляет статус (Normal / Warning / Critical) на основе прогнозируемого времени до переполнения.
2.  **Optimizer (`ai_engine/optimizer.py`):** Решает классическую задачу маршрутизации (VRP). Находит оптимальный путь для мусоровоза, минимизируя общее расстояние между всеми критическими точками.
3.  **Interpreter (LLM):** Преобразует сухие данные в ответы на три главных вопроса:
    * *Что происходит?*
    * *Насколько это критично?*
    * *Что предпринять?*

---

## 🚀 Быстрый старт

### 1. Подготовка окружения
Рекомендуется использовать виртуальное окружение Python:
```bash
python -m venv venv
source venv/bin/activate  # Для Windows: .\venv\Scripts\activate
pip install -r requirements.txt

2. Запуск Backend
Bash
cd backend
uvicorn app.main:app --reload
3. Запуск Frontend
Bash
cd frontend
npm install
npm start
📊 Ожидаемый эффект
-25% Расходов на ГСМ и амортизацию техники.

99% Гарантия чистоты (баки вывозятся до того, как переполнятся).

100% Автоматизация отчетности для городских служб.

👥 Команда
[Марлен Орынтай] — AI/ML Lead, Backend Developer.

[Рахимжан Казтаев] — Frontend Developer, UI/UX Designer.

Разработано в рамках хакатона 2026.
