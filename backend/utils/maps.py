import httpx
import asyncio

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",  # backup
]
OSRM_URL = "https://router.project-osrm.org"
HEADERS = {"User-Agent": "OrderBot-TestingFramework/1.0"}


async def geocode_address(address: str) -> dict | None:
    """Convert address string → lat/lng using Nominatim."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{NOMINATIM_URL}/search",
                params={"q": address, "format": "json", "limit": 1},
                headers=HEADERS
            )
            results = resp.json()
            if results:
                r = results[0]
                return {
                    "lat": float(r["lat"]),
                    "lng": float(r["lon"]),
                    "formatted_address": r.get("display_name", address)
                }
    except Exception:
        pass
    return None


async def reverse_geocode(lat: float, lng: float) -> str | None:
    """Convert lat/lng → human-readable address using Nominatim."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{NOMINATIM_URL}/reverse",
                params={"lat": lat, "lon": lng, "format": "json"},
                headers=HEADERS
            )
            data = resp.json()
            return data.get("display_name")
    except Exception:
        pass
    return None


async def _run_overpass_query(query: str) -> dict | None:
    """Try each Overpass mirror until one works."""
    for url in OVERPASS_URLS:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    url,
                    data={"data": query},
                    headers=HEADERS
                )
                if resp.status_code == 200 and resp.content:
                    return resp.json()
        except Exception:
            continue
    return None


async def search_nearby_restaurants(lat: float, lng: float,
                                     query: str = "restaurant",
                                     radius: int = 2000) -> list:
    """Find real restaurants near coordinates using Overpass API."""

    cuisine_map = {
        "pizza":        'cuisine="pizza"',
        "burger":       'cuisine="burger"',
        "biryani":      'cuisine="indian"',
        "chinese":      'cuisine="chinese"',
        "south indian": 'cuisine="south_indian"',
        "north indian": 'cuisine="indian"',
        "italian":      'cuisine="italian"',
        "cafe":         'amenity="cafe"',
        "bakery":       'amenity="bakery"',
        "seafood":      'cuisine="seafood"',
        "fast food":    'amenity="fast_food"',
    }

    tag_filter = cuisine_map.get(query.lower(), 'amenity="restaurant"')

    # Primary query
    overpass_query = f"""
[out:json][timeout:15];
(
  node[{tag_filter}](around:{radius},{lat},{lng});
  way[{tag_filter}](around:{radius},{lat},{lng});
);
out center 10;
"""
    data = await _run_overpass_query(overpass_query)

    # Fallback: broader search if nothing returned
    if not data or not data.get("elements"):
        fallback_query = f"""
[out:json][timeout:15];
(
  node[amenity~"restaurant|cafe|fast_food|food_court"](around:{radius},{lat},{lng});
  way[amenity~"restaurant|cafe|fast_food|food_court"](around:{radius},{lat},{lng});
);
out center 10;
"""
        data = await _run_overpass_query(fallback_query)

    if not data:
        return []

    results = []
    for el in data.get("elements", [])[:8]:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        elat = el.get("lat") or el.get("center", {}).get("lat")
        elng = el.get("lon") or el.get("center", {}).get("lon")
        if not elat or not elng:
            continue

        cuisine  = tags.get("cuisine", "").replace(";", ", ").replace("_", " ").title()
        opening  = tags.get("opening_hours", "")
        phone    = tags.get("phone", tags.get("contact:phone", ""))
        addr     = " ".join(filter(None, [
            tags.get("addr:housenumber", ""),
            tags.get("addr:street", ""),
            tags.get("addr:city", "")
        ])).strip()

        results.append({
            "place_id":      el.get("id"),
            "name":          name,
            "address":       addr or "Nearby",
            "cuisine":       cuisine or "Restaurant",
            "rating":        "N/A",
            "open_now":      None,
            "opening_hours": opening,
            "phone":         phone,
            "lat":           elat,
            "lng":           elng,
        })

    return results


async def search_nearby_hotels(lat: float, lng: float,
                                radius: int = 5000) -> list:
    """Find real hotels near coordinates using Overpass API."""

    overpass_query = f"""
[out:json][timeout:15];
(
  node[tourism~"hotel|hostel|guest_house|motel"](around:{radius},{lat},{lng});
  way[tourism~"hotel|hostel|guest_house|motel"](around:{radius},{lat},{lng});
);
out center 10;
"""
    data = await _run_overpass_query(overpass_query)

    if not data:
        return []

    results = []
    price_map = {"1": "₹", "2": "₹₹", "3": "₹₹₹", "4": "₹₹₹₹", "5": "₹₹₹₹₹"}

    for el in data.get("elements", [])[:8]:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        elat = el.get("lat") or el.get("center", {}).get("lat")
        elng = el.get("lon") or el.get("center", {}).get("lon")
        if not elat or not elng:
            continue

        stars   = tags.get("stars", "")
        phone   = tags.get("phone", tags.get("contact:phone", ""))
        website = tags.get("website", tags.get("contact:website", ""))
        tourism = tags.get("tourism", "hotel").replace("_", " ").title()
        addr    = " ".join(filter(None, [
            tags.get("addr:housenumber", ""),
            tags.get("addr:street", ""),
            tags.get("addr:city", "")
        ])).strip()

        results.append({
            "place_id":    el.get("id"),
            "name":        name,
            "address":     addr or "Nearby",
            "type":        tourism,
            "rating":      f"{stars} ⭐" if stars else "N/A",
            "price_level": price_map.get(stars, "N/A"),
            "phone":       phone,
            "website":     website,
            "open_now":    None,
            "lat":         elat,
            "lng":         elng,
        })

    return results


async def get_distance_and_eta(origin_lat: float, origin_lng: float,
                                dest_lat: float, dest_lng: float) -> dict | None:
    """Get driving distance and ETA using OSRM."""
    try:
        url = (
            f"{OSRM_URL}/route/v1/driving/"
            f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
            f"?overview=false"
        )
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=HEADERS)
            data = resp.json()

        if data.get("code") == "Ok" and data.get("routes"):
            route        = data["routes"][0]
            distance_m   = route["distance"]
            duration_s   = route["duration"]

            distance_km  = distance_m / 1000
            distance_str = f"{distance_km:.1f} km" if distance_km >= 1 else f"{int(distance_m)} m"

            duration_min = int(duration_s / 60)
            duration_str = f"{duration_min} mins" if duration_min < 60 else f"{duration_min//60}h {duration_min%60}m"

            return {
                "distance":       distance_str,
                "duration":       duration_str,
                "distance_value": distance_m,
                "duration_value": duration_s,
            }
    except Exception:
        pass
    return None


def get_maps_embed_url(lat: float, lng: float, zoom: int = 15) -> str:
    """Return an OpenStreetMap embed URL."""
    delta = 0.01
    return (
        f"https://www.openstreetmap.org/export/embed.html"
        f"?bbox={lng-delta},{lat-delta},{lng+delta},{lat+delta}"
        f"&layer=mapnik&marker={lat},{lng}"
    )


def get_directions_url(origin_lat: float, origin_lng: float,
                        dest_lat: float, dest_lng: float) -> str:
    """Return an OpenStreetMap directions URL."""
    return (
        f"https://www.openstreetmap.org/directions"
        f"?engine=osrm_car&route={origin_lat},{origin_lng};{dest_lat},{dest_lng}"
    )