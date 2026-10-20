# Places, peaks and routes

Never sculpt a real mountain from memory. If the user has elevation data (an ASCII grid or XYZ
export, for example swissALTI3D or Copernicus GLO-30) or can get it, build the place with:

```bash
python3 TOOLS terrain --dem tile.asc|tiles/ --center LAT,LON --extent METRES --title "Name" \
    --source-title "dataset, attribution" [--gpx route.gpx] [--mark "Summit=LAT,LON"] [--from NE] --output place.json
```

It writes a scene with a verified `terrain` part (MEASURED TERRAIN), the route draped on it,
markers, the facts and a view from the side you name; `check`, `review` and adjust the view.
Without data, a small hand-made `terrain` heightfield is allowed but stays `inferred` and shows
as SKETCHED TERRAIN — say so. Attribution for the data goes in `--source-title`; it is shown
on the construct. `--dem` takes several tiles or a folder of them; only the area is read. Details:
docs/TERRAIN.md in the repository.
