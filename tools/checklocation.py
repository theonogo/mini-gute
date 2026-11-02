"""Check the configured coordinates are actually where the name says.

A sign error is the most likely mistake anyone makes typing coordinates, and a
swapped latitude and longitude is the second. Both produce a valid point on the
globe, so no amount of range checking catches them, and nothing complains: the
weather slots fetch a real forecast for a real place a few hundred kilometres
away and print it every morning under the right name, which is exactly the
kind of wrong that looks right. The only real check is to ask where the NAME is
and measure the distance.

Uses Open-Meteo's geocoder, which is free and unauthenticated. This runs on
demand, not every morning: a network call at startup is a new way for the print
to fail, and coordinates do not change on their own.

    python tools/checklocation.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from sources.http import get_json  # noqa: E402

# A named town and its own coordinates can legitimately sit a few kilometres
# apart - the geocoder returns a centroid. Past this, something is wrong.
TOLERANCE_KM = 40


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def main() -> int:
    lat, lon, name = config.location()
    print(f"configured:  {name!r} at {lat}, {lon}")
    if not name:
        print("No QG_LOCATION_NAME set, so there is nothing to check against.")
        return 0

    data = get_json("https://geocoding-api.open-meteo.com/v1/search"
                    f"?name={quote(name)}&count=5&format=json")
    results = data.get("results") or []
    if not results:
        print(f"The geocoder does not recognise {name!r}; cannot check.")
        return 0

    best = min(results, key=lambda r: haversine_km(lat, lon, r["latitude"],
                                                   r["longitude"]))
    distance = haversine_km(lat, lon, best["latitude"], best["longitude"])
    print(f"geocoded:    {best['name']}, {best.get('country', '?')} at "
          f"{best['latitude']:.4f}, {best['longitude']:.4f}")
    print(f"distance:    {distance:,.0f} km")

    if distance <= TOLERANCE_KM:
        print("\nOK - the coordinates are where the name says.")
        return 0

    print(f"\nMISMATCH - the coordinates are {distance:,.0f} km from {name}.")
    # The two mistakes that produce a valid-looking point: a flipped sign and a
    # swapped pair. Name the one that fits, because "your location is wrong" is
    # far less useful than "your longitude has the wrong sign".
    for label, (tlat, tlon) in (("longitude sign flipped", (lat, -lon)),
                                ("latitude sign flipped", (-lat, lon)),
                                ("latitude and longitude swapped", (lon, lat))):
        if haversine_km(tlat, tlon, best["latitude"],
                        best["longitude"]) <= TOLERANCE_KM:
            print(f"Likely cause: {label}. Try {tlat}, {tlon}.")
            break
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
