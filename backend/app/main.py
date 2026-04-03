from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import random

app = FastAPI()

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
    # Almaty center coordinates (more precise)
    base_lat = 43.2389  # центр города
    base_lng = 76.9455  # центр города
    # Radius: ±0.10 degrees ≈ 11 km (covers entire city properly)
    for i in range(50):
        items.append({
            "id": i,
            "lat": base_lat + random.uniform(-0.10, 0.10),
            "lng": base_lng + random.uniform(-0.10, 0.10),
            "fill_level": random.randint(0, 100)
        })
    return items
