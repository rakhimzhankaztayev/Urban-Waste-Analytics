"""
optimizer.py
Solves the Vehicle Routing Problem (VRP) for waste collection trucks.

Algorithm: Greedy Nearest-Neighbor (good balance of speed and quality for
hackathon scale). Falls back gracefully — no heavy external dependencies.

For production, swap `_greedy_tsp` with Google OR-Tools VRP solver.
"""

from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class BinLocation:
    bin_id: str
    latitude: float
    longitude: float
    fill_level: float
    status: str          # "Normal" | "Warning" | "Critical"
    district: str = ""


@dataclass
class RouteStop:
    order: int
    bin_id: str
    latitude: float
    longitude: float
    district: str
    fill_level: float
    distance_from_prev_km: float


@dataclass
class OptimizedRoute:
    truck_id: str
    start_point: dict           # {"latitude": ..., "longitude": ...}
    stops: list[RouteStop]
    total_distance_km: float
    estimated_duration_min: int
    bins_count: int


class RouteOptimizer:
    """
    Builds optimized collection routes for one or more trucks.

    Priority rules:
    - Critical bins (>85%) MUST be visited.
    - Warning bins (60–85%) are included if truck capacity allows.
    - Normal bins are skipped.

    Average truck speed assumed at 30 km/h in city conditions.
    """

    AVERAGE_SPEED_KMH = 30
    STOP_SERVICE_TIME_MIN = 5      # time to empty one bin

    def __init__(self, include_warning: bool = True):
        self.include_warning = include_warning

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def optimize(
        self,
        bins: list[BinLocation],
        start_point: dict,
        truck_id: str = "TRUCK-01",
        max_stops: Optional[int] = None,
    ) -> OptimizedRoute:
        """
        bins: all bins in the system.
        start_point: {"latitude": float, "longitude": float} — truck depot/current location.
        """
        candidates = self._filter_candidates(bins)

        if not candidates:
            logger.info("No bins require collection.")
            return OptimizedRoute(
                truck_id=truck_id,
                start_point=start_point,
                stops=[],
                total_distance_km=0.0,
                estimated_duration_min=0,
                bins_count=0,
            )

        if max_stops:
            # Prioritize Critical first, then Warning
            candidates.sort(key=lambda b: (0 if b.status == "Critical" else 1, -b.fill_level))
            candidates = candidates[:max_stops]

        ordered = self._greedy_tsp(candidates, start_point)
        route_stops, total_km = self._build_stops(ordered, start_point)

        drive_min = (total_km / self.AVERAGE_SPEED_KMH) * 60
        service_min = len(route_stops) * self.STOP_SERVICE_TIME_MIN
        total_min = int(drive_min + service_min)

        return OptimizedRoute(
            truck_id=truck_id,
            start_point=start_point,
            stops=route_stops,
            total_distance_km=round(total_km, 2),
            estimated_duration_min=total_min,
            bins_count=len(route_stops),
        )

    def optimize_multi_truck(
        self,
        bins: list[BinLocation],
        trucks: list[dict],       # [{"truck_id": str, "latitude": float, "longitude": float}]
        max_stops_per_truck: int = 15,
    ) -> list[OptimizedRoute]:
        """
        Distributes bins across multiple trucks.
        Simple strategy: assign each bin to the nearest available truck.
        """
        candidates = self._filter_candidates(bins)
        candidates.sort(key=lambda b: (0 if b.status == "Critical" else 1, -b.fill_level))

        # Assign bins round-robin weighted by distance
        assignments: dict[str, list[BinLocation]] = {t["truck_id"]: [] for t in trucks}

        for b in candidates:
            best_truck = min(
                trucks,
                key=lambda t: self._haversine(
                    t["latitude"], t["longitude"], b.latitude, b.longitude
                ),
            )
            tid = best_truck["truck_id"]
            if len(assignments[tid]) < max_stops_per_truck:
                assignments[tid].append(b)

        routes = []
        for truck in trucks:
            tid = truck["truck_id"]
            start = {"latitude": truck["latitude"], "longitude": truck["longitude"]}
            route = self.optimize(assignments[tid], start, truck_id=tid)
            routes.append(route)

        return routes

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _filter_candidates(self, bins: list[BinLocation]) -> list[BinLocation]:
        statuses = {"Critical"}
        if self.include_warning:
            statuses.add("Warning")
        return [b for b in bins if b.status in statuses]

    def _greedy_tsp(self, bins: list[BinLocation], start: dict) -> list[BinLocation]:
        """
        Nearest-neighbor heuristic.
        Starting from `start`, always visit the closest unvisited bin next.
        """
        unvisited = list(bins)
        route: list[BinLocation] = []
        current_lat = start["latitude"]
        current_lon = start["longitude"]

        while unvisited:
            nearest = min(
                unvisited,
                key=lambda b: self._haversine(current_lat, current_lon, b.latitude, b.longitude),
            )
            route.append(nearest)
            unvisited.remove(nearest)
            current_lat = nearest.latitude
            current_lon = nearest.longitude

        return route

    def _build_stops(
        self, ordered: list[BinLocation], start: dict
    ) -> tuple[list[RouteStop], float]:
        stops = []
        total_km = 0.0
        prev_lat = start["latitude"]
        prev_lon = start["longitude"]

        for i, b in enumerate(ordered):
            dist = self._haversine(prev_lat, prev_lon, b.latitude, b.longitude)
            total_km += dist
            stops.append(
                RouteStop(
                    order=i + 1,
                    bin_id=b.bin_id,
                    latitude=b.latitude,
                    longitude=b.longitude,
                    district=b.district,
                    fill_level=b.fill_level,
                    distance_from_prev_km=round(dist, 3),
                )
            )
            prev_lat = b.latitude
            prev_lon = b.longitude

        return stops, total_km

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Returns distance in km between two GPS coordinates."""
        R = 6371.0
        φ1, φ2 = radians(lat1), radians(lat2)
        Δφ = radians(lat2 - lat1)
        Δλ = radians(lon2 - lon1)
        a = sin(Δφ / 2) ** 2 + cos(φ1) * cos(φ2) * sin(Δλ / 2) ** 2
        return R * 2 * atan2(sqrt(a), sqrt(1 - a))
