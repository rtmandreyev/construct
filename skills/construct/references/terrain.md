# Places, peaks and routes

Never sculpt a real mountain from memory. If the user has elevation data (an ASCII grid or XYZ
export, for example swissALTI3D or Copernicus GLO-30) or can get it, build the place with:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/cli.py terrain --dem tile.asc|tiles/ --center LAT,LON --extent METRES --title "Name" \
    --source-title "dataset, attribution" [--gpx route.gpx] [--mark "Summit=LAT,LON"] [--from NE] --output place.json
```

It writes a scene with a verified `terrain` part (MEASURED TERRAIN), the route draped on it,
markers, the facts and a view from the side you name; `check`, `review` and adjust the view.
Without data, a small hand-made `terrain` heightfield is allowed but stays `inferred` and shows
as SKETCHED TERRAIN — say so. Attribution for the data goes in `--source-title`; it is shown
on the construct. `--dem` takes several tiles or a folder of them; only the area is read. Details:
docs/TERRAIN.md in the repository.

## The globe

Never draw Earth's continents from memory as if measured. With coastline data (GeoJSON, for
example Natural Earth's public-domain `ne_110m_coastline.geojson`):

```bash
python3 ${HERMES_SKILL_DIR}/scripts/cli.py globe --coastlines coast.geojson --title "Earth" \
    --source-title "Natural Earth 1:110m coastline (public domain)" --output earth.json
```

It writes a sphere, the coastlines (verified: MEASURED COASTLINES), the axis at the cited
23.44° tilt and a slow spin. Without data, a hand-made globe is a sketch: `inferred`
coastlines and `accuracy` approximate at most; say so.
