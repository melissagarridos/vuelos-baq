# ✈ VuelosBAQ — Buscador de vuelos económicos desde Barranquilla

Página web estática (GitHub Pages) que muestra ofertas de vuelos internacionales desde **Barranquilla (BAQ)**, con actualización automática diaria de precios vía GitHub Actions y alertas visuales de **súper descuentos** (≥30% bajo el precio típico).

## Características

- Buscador con enlaces directos a Google Flights, Skyscanner y Kayak con la ruta prellenada.
- Tarjetas de ofertas del día para 15 destinos populares (Miami, Panamá, CDMX, Madrid, Lima, etc.).
- Banner de alerta cuando hay súper descuentos.
- Bot (GitHub Actions) que consulta la API gratuita de Travelpayouts cada día a las 6:00 a.m. (Colombia) y actualiza `data/deals.json`.

## Estructura

```
vuelos-baq/
├── index.html                      # La página web
├── data/deals.json                 # Ofertas (se actualiza automáticamente)
├── scripts/update_deals.py         # Script que consulta la API
└── .github/workflows/update-deals.yml  # Automatización diaria
```

## Cómo publicarlo

1. Crea un repositorio en GitHub (por ejemplo `vuelos-baq`) y sube todos los archivos:
   ```bash
   cd vuelos-baq
   git init && git add . && git commit -m "Primer commit"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/vuelos-baq.git
   git push -u origin main
   ```
2. En GitHub: **Settings → Pages → Source: Deploy from a branch → main / (root)** → Save.
3. Tu página quedará en `https://TU_USUARIO.github.io/vuelos-baq/`.

## Activar la actualización automática de precios

1. Regístrate gratis en [Travelpayouts](https://www.travelpayouts.com/) y copia tu **API token** (Perfil → API token).
2. En tu repositorio: **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `TRAVELPAYOUTS_TOKEN`
   - Secret: tu token
3. Ve a la pestaña **Actions**, habilita los workflows y ejecuta "Actualizar ofertas de vuelos" manualmente (Run workflow) para probar.

Mientras no configures el token, la página muestra los datos de ejemplo de `data/deals.json`.

## Personalización

- **Destinos**: edita la lista `DESTINATIONS` en `scripts/update_deals.py` y el `<select id="dest">` en `index.html`.
- **Umbral de súper descuento**: cambia `SUPER_DISCOUNT` en `index.html` (por defecto 30%).
- **Precios típicos** (base del % de descuento): ajusta `TYPICAL_PRICES` en el script.
- **Horario**: cambia el `cron` en `.github/workflows/update-deals.yml`.

## Nota

Los precios son referenciales (datos en caché de Aviasales) y pueden variar al reservar.
