"""
Lightweight geo helpers for estimating how far a supplier is from an institution and how
long delivery should take. There's no live GPS/routing integration — distance is computed
"as the crow flies" between county centroids (see core.models.County), then padded by a
road-windiness factor and converted to a travel time estimate at a realistic produce-truck
speed. It's an estimate, not a precise ETA, and is labelled as such wherever it's shown.
"""
import math
from functools import lru_cache

from .models import County

EARTH_RADIUS_KM = 6371.0
# Straight-line distance underestimates actual road distance — Kenyan roads are rarely
# straight. This multiplier brings the estimate closer to a realistic driving distance.
ROAD_WINDINESS_FACTOR = 1.35
# Assumed average speed for a produce delivery vehicle, accounting for loading, county
# roads, and town traffic — not highway speed.
AVERAGE_DELIVERY_SPEED_KMH = 35.0
# Fixed handling/loading buffer added to every delivery, regardless of distance.
HANDLING_BUFFER_HOURS = 1.5


@lru_cache(maxsize=64)
def county_coordinates(county_name):
    """(lat, lng) for a county name, or None if unknown/unset."""
    if not county_name:
        return None
    county = County.objects.filter(name__iexact=county_name).first()
    if not county or county.latitude is None or county.longitude is None:
        return None
    return (county.latitude, county.longitude)


def haversine_km(coord_a, coord_b):
    lat1, lng1 = coord_a
    lat2, lng2 = coord_b
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def estimate_distance_and_eta(from_county, to_county):
    """
    Returns a dict with distance_km and estimated_delivery_hours between two counties, or
    None for either figure if either county's coordinates aren't known. Same county still
    returns a small non-zero distance/time (intra-county delivery isn't instant).
    """
    coord_a = county_coordinates(from_county)
    coord_b = county_coordinates(to_county)
    if not coord_a or not coord_b:
        return {"distance_km": None, "estimated_delivery_hours": None}

    if from_county.strip().lower() == to_county.strip().lower():
        # Same county: assume a short average in-county hop rather than 0km.
        distance_km = 18.0
    else:
        straight_line = haversine_km(coord_a, coord_b)
        distance_km = round(straight_line * ROAD_WINDINESS_FACTOR, 1)

    hours = HANDLING_BUFFER_HOURS + (distance_km / AVERAGE_DELIVERY_SPEED_KMH)
    return {"distance_km": distance_km, "estimated_delivery_hours": round(hours, 1)}


def county_location(county_name):
    """{"county": ..., "latitude": ..., "longitude": ...} for map display, or None coords if unknown."""
    coords = county_coordinates(county_name)
    return {
        "county": county_name,
        "latitude": coords[0] if coords else None,
        "longitude": coords[1] if coords else None,
    }
