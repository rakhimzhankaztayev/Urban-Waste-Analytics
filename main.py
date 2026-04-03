# main.py
from fastapi import FastAPI
from ai_engine.router import router as ai_router

app = FastAPI(title="Smart Waste AI - Dev Server")


@app.get("/")
def root() -> dict[str, str]:
	return {
		"message": "Smart Waste AI API is running",
		"docs": "/docs",
		"health": "/api/v1/ai/health",
	}


app.include_router(ai_router, prefix="/api/v1/ai", tags=["AI Engine"])