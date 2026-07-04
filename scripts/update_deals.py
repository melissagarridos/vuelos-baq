#!/usr/bin/env python3
"""
Actualiza data/deals.json con los precios más baratos en rutas nacionales e
internacionales desde Barranquilla (BAQ), Cartagena (CTG) y Bogotá (BOG).

Fuentes:
1. Travelpayouts / Aviasales (obligatoria) — TRAVELPAYOUTS_TOKEN.
2. SerpApi / Google Flights (opcional)  — SERPAPI_KEY.
   Cubre low-cost como Wingo, JetSMART y Clic. El plan gratis da 100
   búsquedas/mes, así que solo se consultan SERPAPI_DAILY_LIMIT rutas por
   corrida, rotando cada día; se conserva el precio más bajo de ambas fuentes.

Uso local:
  TRAVELPAYOUTS_TOKEN=xxx SERPAPI_KEY=yyy python scripts/update_deals.py
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

TOKEN = os.environ.get("TRAVELPAYOUTS_TOKEN", "")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
SERPAPI_DAILY_LIMIT = int(os.environ.get("SERPAPI_DAILY_LIMIT", "3"))
CURRENCY = "cop"

ORIGINS = ["BAQ", "CTG", "BOG"]

NATIONAL = ["BOG", "MDE", "CLO", "CTG", "BAQ", "SMR", "ADZ", "PEI", "BGA", "CUC"]
INTERNATIONAL = ["MIA", "FLL", "MCO", "JFK", "PTY", "MEX", "CUN", "LIM",
                 "SCL", "EZE", "SJO", "MAD", "BCN", "CUR", "AUA", "PUJ", "UIO"]

# Precios "típicos" por trayecto en COP para calcular % de descuento.
# Clave: (origen, destino). Si una ruta no está, se usa TYPICAL_DEFAULT.
TYPICAL_NATIONAL = {
    "BOG": 250_000, "MDE": 250_000, "CLO": 280_000, "CTG": 250_000,
    "BAQ": 250_000, "SMR": 250_000, "ADZ": 400_000, "PEI": 280_000,
    "BGA": 280_000, "CUC": 300_000,
}
TYPICAL_INTERNATIONAL = {
    "MIA": 900_000, "FLL": 850_000, "MCO": 950_000, "JFK": 1_300_000,
    "PTY": 600_000, "MEX": 1_100_000, "CUN": 1_000_000, "LIM": 900_000,
    "SCL": 1_500_000, "EZE": 1_800_000, "SJO": 900_000, "MAD": 2_800_000,
    "BCN": 3_000_000, "CUR": 800_000, "AUA": 800_000, "PUJ": 1_000_000,
    "UIO": 800_000,
}
# Ajuste por origen (Bogotá suele ser algo más barato por mayor oferta).
ORIGIN_FACTOR = {"BAQ": 1.0, "CTG": 1.0, "BOG": 0.9}

API = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
OUT = Path(__file__).resolve().parent.parent / "data" / "deals.json"


def typical_price(origin: str, dest: str, scope: str) -> float:
    base = (TYPICAL_NATIONAL if scope == "national" else TYPICAL_INTERNATIONAL).get(dest, 0)
    return base * ORIGIN_FACTOR.get(origin, 1.0)


def fetch_cheapest(origin: str, dest: str, scope: str) -> dict | None:
    params = urllib.parse.urlencode({
        "origin": origin,
        "destination": dest,
        "currency": CURRENCY,
        "sorting": "price",
        "direct": "false",
        "limit": 1,
        "one_way": "true",
        "token": TOKEN,
    })
    try:
        with urllib.request.urlopen(f"{API}?{params}", timeout=30) as r:
            payload = json.load(r)
    except Exception as e:
        print(f"  [WARN] {origin}->{dest}: {e}", file=sys.stderr)
        return None

    items = payload.get("data") or []
    if not items:
        return None
    it = items[0]
    price = float(it["price"])
    typical = typical_price(origin, dest, scope)
    discount = round(max(0.0, (1 - price / typical) * 100), 1) if typical else 0.0
    return {
        "origin": origin,
        "destination": dest,
        "scope": scope,
        "price": price,
        "currency": "COP",
        "departure_date": it.get("departure_at", "")[:10],
        "airline": it.get("airline", ""),
        "transfers": it.get("transfers", None),
        "discount_pct": discount,
        "link": "https://www.aviasales.com" + it["link"] if it.get("link") else "",
        "source": "aviasales",
    }


# ---------- SerpApi / Google Flights ----------
SERPAPI_URL = "https://serpapi.com/search.json"


def fetch_google_flights(origin: str, dest: str, dep_date: str) -> dict | None:
    """Precio más bajo en Google Flights para una ruta y fecha (solo ida)."""
    params = urllib.parse.urlencode({
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": dest,
        "outbound_date": dep_date,
        "type": "2",              # solo ida
        "currency": "COP",
        "hl": "es",
        "api_key": SERPAPI_KEY,
    })
    try:
        with urllib.request.urlopen(f"{SERPAPI_URL}?{params}", timeout=45) as r:
            payload = json.load(r)
    except Exception as e:
        print(f"  [WARN] SerpApi {origin}->{dest}: {e}", file=sys.stderr)
        return None

    options = (payload.get("best_flights") or []) + (payload.get("other_flights") or [])
    options = [o for o in options if o.get("price")]
    if not options:
        return None
    best = min(options, key=lambda o: o["price"])
    legs = best.get("flights") or []
    return {
        "price": float(best["price"]),
        "airline": legs[0].get("airline", "") if legs else "",
        "transfers": max(0, len(legs) - 1),
        "link": f"https://www.google.com/travel/flights?q="
                f"{urllib.parse.quote(f'Flights from {origin} to {dest} on {dep_date} one way')}&curr=COP",
    }


def rotation_slice(deals: list, limit: int) -> list:
    """Subconjunto de rutas a verificar hoy con SerpApi (rota cada día)."""
    if not deals or limit <= 0:
        return []
    start = (date.today().toordinal() * limit) % len(deals)
    return [deals[(start + i) % len(deals)] for i in range(min(limit, len(deals)))]


def enrich_with_google(deals: list) -> None:
    """Compara con Google Flights las rutas del turno de hoy y guarda el menor precio."""
    if not SERPAPI_KEY:
        print("SERPAPI_KEY no configurada: se omite Google Flights.")
        return
    for deal in rotation_slice(deals, SERPAPI_DAILY_LIMIT):
        dep = deal.get("departure_date") or (date.today() + timedelta(days=30)).isoformat()
        print(f"Verificando en Google Flights {deal['origin']} -> {deal['destination']} ({dep})...")
        g = fetch_google_flights(deal["origin"], deal["destination"], dep)
        if g and g["price"] < deal["price"]:
            typical = typical_price(deal["origin"], deal["destination"], deal["scope"])
            deal.update({
                "price": g["price"],
                "airline": g["airline"],
                "transfers": g["transfers"],
                "link": g["link"],
                "source": "google_flights",
                "discount_pct": round(max(0.0, (1 - g["price"] / typical) * 100), 1) if typical else 0.0,
            })
            print(f"  Mejor precio en Google Flights: {g['price']:,.0f} COP ({g['airline']})")


def main() -> None:
    if not TOKEN:
        print("ERROR: falta TRAVELPAYOUTS_TOKEN", file=sys.stderr)
        sys.exit(1)

    deals = []
    for origin in ORIGINS:
        for dest in NATIONAL:
            if dest == origin:
                continue
            print(f"Consultando {origin} -> {dest} (nacional)...")
            deal = fetch_cheapest(origin, dest, "national")
            if deal:
                deals.append(deal)
        for dest in INTERNATIONAL:
            print(f"Consultando {origin} -> {dest} (internacional)...")
            deal = fetch_cheapest(origin, dest, "international")
            if deal:
                deals.append(deal)

    enrich_with_google(deals)

    deals.sort(key=lambda d: (d["origin"], -d["discount_pct"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "origins": ORIGINS,
        "deals": deals,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(deals)} ofertas guardadas en {OUT}")


if __name__ == "__main__":
    main()
