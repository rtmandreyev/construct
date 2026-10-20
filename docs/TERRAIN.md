# Terrain: places, peaks and routes

A place is built from elevation data you supply, not drawn from memory. `construct terrain`
samples the data deterministically into a `terrain` construct, drapes your route on it, marks
the points you name, and labels the result **MEASURED TERRAIN** with its scale and its data
source. A relief made by hand (no data) stays `inferred` and is labelled **SKETCHED TERRAIN**.

```sh
python3 construct_hologram/cli.py terrain --dem swissalti3d-tiles/ --center 45.97636,7.65861 --extent 3200 \
    --title "Matterhorn" --source-title "swissALTI3D, ©swisstopo" \
    --gpx hornli.gpx --mark "Summit=45.9763,7.6586" --from NE --output matterhorn.json
python3 construct_hologram/cli.py review matterhorn.json --out out
```

## Elevation data

Construct reads two plain formats and never downloads anything:

- **ESRI ASCII grid** (`.asc`): `ncols`, `nrows`, `xllcorner`/`xllcenter`, `yllcorner`/`yllcenter`,
  `cellsize`, optional `NODATA_value`, then the rows from north to south.
- **XYZ text** (`.xyz`, `.txt`, `.csv`): one `x y z` per line on a regular grid (headers are
  skipped).

A GeoTIFF is converted first, for example `gdal_translate -of AAIGrid tile.tif tile.asc`.

`--dem` takes one file, several, or a folder of tiles of one dataset (`--dem tiles/`). Only the
requested area is kept, thinned to the sampling resolution while reading, so a massif from
twenty 2 m swissALTI3D tiles (5 million points, 119 MB of text) builds in about 5 seconds and
35 MB of memory. The elevation facts report the data's own lowest and highest points inside
the area — the summit, not the highest sample. The relief is resampled onto at most 100 cells
per side, which keeps it inside the 24,000-triangle budget.

Tested against swissALTI3D 2024 (© swisstopo) around the Matterhorn: summit 4477.2 m as in the
data; the Hörnli hut marker sits on the NE ridge. The tiles are never committed; to run that
test, point `CONSTRUCT_TEST_MATTERHORN_DEM` at a folder of the XYZ tiles (LV95, E 2615–2619 km,
N 1090–1093 km).

Reference systems: Swiss LV95 (`EPSG:2056`, swisstopo's approximate formulas, about 1 m), UTM
(`EPSG:326xx` north / `EPSG:327xx` south), or longitude/latitude degrees (`EPSG:4326`).
`--crs` names it; LV95 and degrees are recognised from the coordinates. Routes (GPX), `--center`
and `--mark` are WGS84 latitude/longitude and are converted.

### Sources and their terms (check the current terms before you publish)

| data | coverage | terms |
|---|---|---|
| swisstopo **swissALTI3D**, **DHM25** | Switzerland | free geodata, commercial use allowed; attribution required: "©swisstopo" or "Federal Office of Topography swisstopo" ([terms of use](https://www.swisstopo.admin.ch/en/terms-of-use-free-geodata-and-geoservices)) |
| **Copernicus DEM GLO-30** | worldwide (except Armenia and Azerbaijan) | free use under the Copernicus DEM licence; the licence's attribution notice and its liability disclaimer must accompany distribution, and derived products carry the notice the licence gives for them ([licence](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf)) |

Put the attribution in `--source-title`: the construct shows it as **DATA:** under the
caption, and the scene records it as a `dataset` source.

## Scale ladder

Each place is shown at the scale of its class, so a sea cliff, a valley and a range each read at
their own size and still fit their region:

| class | extent | stage width |
|---|---|---|
| spot | up to 100 m | 1 m |
| site | up to 1 km | 2 m |
| valley | up to 8 km | 4 m |
| massif | up to 30 km | 8 m |
| range | beyond | 16 m |

`--class` overrides the class; `--exaggeration` raises the heights (stated on the construct as
HEIGHTS ×n; 1 means true heights). The facts record the extent, the lowest and highest
elevation (verified, from the data), the class and the scale.

## Measured and sketched

- **MEASURED TERRAIN:** the `terrain` part is `verified` and cites a source of kind `dataset`.
- **SKETCHED TERRAIN:** a hand-made heightfield is `inferred` (a guidebook or a photo is not
  elevation data). The audit's `shape-overclaim` refuses a verified relief without a dataset,
  a measurement or a drawing behind it.

Your dates, companions and photos belong with your own notes, not in the place.
