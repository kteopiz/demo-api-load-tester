import csv
import math
from config.bounds import LATITUDE_BOUNDS, LONGITUDE_BOUNDS, COORDS_DECIMAL_PLACES


def generate_random_coords(rng):
    return (
        round(rng.uniform(*LATITUDE_BOUNDS), COORDS_DECIMAL_PLACES),
        round(rng.uniform(*LONGITUDE_BOUNDS), COORDS_DECIMAL_PLACES),
    )


def load_cached_coords(path):
    """Load unique synthetic hot locations, rejecting malformed coordinates."""
    with open(path, newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if not {"latitude", "longitude"}.issubset(reader.fieldnames or []):
            raise ValueError("Location CSV requires latitude and longitude columns")
        coords = []
        for row in reader:
            lat, lon = float(row["latitude"]), float(row["longitude"])
            if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("Invalid location coordinates")
            coords.append((round(lat, COORDS_DECIMAL_PLACES), round(lon, COORDS_DECIMAL_PLACES)))
    if not coords:
        raise ValueError("Location CSV must contain at least one location")
    return list(dict.fromkeys(coords))
