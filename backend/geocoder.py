import re
from geopy.geocoders import Nominatim
from typing import List, Optional, Tuple

# 0.05 degrees is roughly 5km at the equator. 
# A bounding box of +/- 0.05 gives a 10km x 10km square.
BBOX_RADIUS_DEG = 0.05 

def _inflate_point_to_bbox(lat: float, lon: float) -> List[float]:
    """Converts a single GPS point into a 10km x 10km Bounding Box."""
    return [
        round(lon - BBOX_RADIUS_DEG, 4), # min_lon
        round(lat - BBOX_RADIUS_DEG, 4), # min_lat
        round(lon + BBOX_RADIUS_DEG, 4), # max_lon
        round(lat + BBOX_RADIUS_DEG, 4)  # max_lat
    ]

def parse_google_maps_url(url: str) -> Optional[List[float]]:
    """
    Extracts latitude and longitude from common Google Maps URL formats
    and returns a bounding box.
    """
    # Format 1: ?q=lat,lon
    m1 = re.search(r"[?&]q=([\d\.-]+),([\d\.-]+)", url)
    if m1:
        lat, lon = float(m1.group(1)), float(m1.group(2))
        return _inflate_point_to_bbox(lat, lon)
        
    # Format 2: /@lat,lon,
    m2 = re.search(r"@([\d\.-]+),([\d\.-]+),", url)
    if m2:
        lat, lon = float(m2.group(1)), float(m2.group(2))
        return _inflate_point_to_bbox(lat, lon)
        
    return None

def geocode_location(location_name: str) -> Optional[List[float]]:
    """
    Uses OpenStreetMap (Nominatim) to find the GPS point for a text location,
    then inflates it to a bounding box.
    """
    try:
        # Nominatim requires a user_agent
        geolocator = Nominatim(user_agent="infra_ai_satellite_tracker")
        location = geolocator.geocode(location_name)
        
        if location:
            return _inflate_point_to_bbox(location.latitude, location.longitude)
        return None
    except Exception as e:
        print(f"Geocoding failed for '{location_name}': {e}")
        return None

if __name__ == "__main__":
    # Test
    print("Testing Google Maps URL:")
    url = "https://www.google.com/maps/place/Sohna/@28.25,77.06,15z"
    print(parse_google_maps_url(url))
    
    print("\nTesting Geocoder:")
    print(geocode_location("Sohna, Haryana, India"))
