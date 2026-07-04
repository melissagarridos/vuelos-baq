#!/usr/bin/env python3
"""
Actualiza data/deals.json con los precios más baratos desde Barranquilla (BAQ)
usando la API gratuita de Travelpayouts (datos de Aviasales).

Requiere la variable de entorno TRAVELPAYOUTS_TOKEN.
Regístrate gratis en https://www.travelpayouts.com/ para obtener tu token.

Uso local:  TRAVELPAYOUTS_TOKEN=xxx python scripts/update_deals.py
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TOKEN = os.environ.get("TRAVELPAYOUTS_TOKEN", "")
ORIGIN = "BAQ"
CURRENCY = "cop"
DESTINATIONS = ["MIA", "FLL", "MCO", "JFK", "PTY", "MEX", "CUN",
                "LIM", "SCL", "EZE", "SJO", "MAD", "BCN", "CUR", "AUA"]

# Precios "típicos" por trayecto en COP para calcular % de descuento.
TYPICAL_PRICES = {
    "MIA": 900_000, "FLL": 850_000, "MCO": 950_000, "JFK": 1_300_000,
    "PTY": 600_000, "MEX": 1_100_000, "CUN": 1_000_000,
    "LIM": 900_000, "SCL": 1_500_000, "EZE": 1_800_000, "SJO": 900_000,
    "MAD": 2_800_000, "BCN": 3_000_000, "CUR": 800_000, "AUA": 800_000,
}

API = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
OUT = Path(__file__).resolve().parent.parent / "data" / "deals.json"


def fetch_cheapest(dest: str) -> dict | None:
    params = urllib.parse.urlencode({
        "origin": ORIGIN,
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
        print(f"  [WARN] {dest}: {e}", file=sys.stderr)
        return None

    items = payload.get("data") or []
    if not items:
        return None
    it = items[0]
    price = float(it["price"])
    typical = TYPICAL_PRICES.get(dest, 0)
    discount = round(max(0.0, (1 - price / typical) * 100), 1) if typical else 0.0
    return {
        "destination": dest,
        "price": price,
        "currency": "COP",
        "departure_date": it.get("departure_at", "")[:10],
        "airline": it.get("airline", ""),
        "transfers": it.get("transfers", None),
        "discount_pct": discount,
        "link": "https://www.aviasales.com" + it["link"] if it.get("link") else "",
    }


def main() -> None:
    if not TOKEN:
        print("ERROR: falta TRAVELPAYOUTS_TOKEN", file=sys.stderr)
        sys.exit(1)

    deals = []
    for dest in DESTINATIONS:
        print(f"Consultando {ORIGIN} -> {dest}...")
        deal = fetch_cheapest(dest)
        if deal:
            deals.append(deal)

    deals.sort(key=lambda d: d["discount_pct"], reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "origin": ORIGIN,
        "deals": deals,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(deals)} ofertas guardadas en {OUT}")


if __name__ == "__main__":
    main()
