# Milan in 3D, lit by the real sun

Central Milan in the browser: 10,023 buildings from the Comune di Milano's own survey, 1,298 surveyed trees, the 11 tram
lines that cross the centre with trams running on them, people in the piazzas, and street lights hung over the streets as
in Milan. The sun is the real one for any date and time, from the blue hour before sunrise to the floodlit Duomo at night.

**Live:** https://mys1erious.github.io/3d-city-milan/

![Piazza del Duomo at night](poster.jpg)

## What you can do
- Drag the time slider, pick a date (21 Jun / 21 Dec / today), orbit and zoom.
- Hover or tap a building for its name and surveyed height.
- **☀ Sun hours**: how many hours of direct sun every 2 m of street, piazza and courtyard gets on 21 June, 21 December
  or 20 March. Hover or tap a street for its number. On 21 December, 53% of the open ground in the centre gets no direct
  sun at all; on 21 June half of it gets more than 5 h 20 min.

| 21 June | 21 December |
|---|---|
| ![Sun hours on 21 June](sun-june.jpg) | ![Sun hours on 21 December](sun-december.jpg) |

## URL parameters
| Parameter | Effect |
|---|---|
| `?play` | the 24 s day-to-night flyover on 21 June (`&date=YYYY-MM-DD` for another day) |
| `?clean` | hide the controls |
| `&t=SEC` | freeze the flyover at that second |
| `?cam=tx,ty,th,az,el,d&m=MIN&date=...` | a still: camera target in m (x east, y north from the centre), height, bearing and elevation in degrees, distance in m, and the clock in minutes |
| `&heat` | open the sun-hours layer |

## Data
| Source | Used for | Licence |
|---|---|---|
| [Comune di Milano, Database Topografico 2020](https://dati.comune.milano.it/dataset/ds2889_database-topografico-dbt-2020-shp) (layers `UN_VOL`, `ALBERO`) | building volumes and heights, trees | [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/), modified: clipped to a 1.6 km disc and merged with OSM |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | the Duomo's spires, roof shapes (Galleria, Torre Velasca, Castello towers), names, streets, piazzas, parks, tram routes | ODbL, © OpenStreetMap contributors |

Inside the disc the survey has 10,899 building volumes, each with its height and base level, so arcades and raised wings
start above the street. OpenStreetMap is kept where it models a building better (the Duomo's 103 parts up to the 108.5 m
Madonnina; tagged roof forms). For the 15 named buildings that have an OSM height, the survey's tallest volume differs by
2.6 m at the median.

## How it works
- One `index.html` with three.js 0.170 from a CDN: extruded buildings, a façade shader (Milan's stucco colours, windows
  with shutters that light up at night), GTAO contact shadows, bloom, ACES tone mapping.
- **Sun**: NOAA solar-position formulas, checked against astronomy-engine 2.1.19: solar noon altitude in Milan is 31.36°
  on 28 Oct 2026 and 67.98° on 21 Jun; the worst difference over 2026 is 0.02°.
- **Sun hours** (`data/sun_hours.py`): for every 5 minutes with the sun up, a ray from each 2 m cell, 1 m above the
  ground, marches towards the sun over a height grid of the buildings. Trees are not counted. Buildings outside the disc
  are missing, so the page fades the outer 140 m and the numbers above use the inner 660 m.

## Rebuild the data
```sh
cd data
# 1. buildings and trees from the Comune's DBT 2020 shapefiles (597 MB zip, unzip the "DBT 2020 - SHAPE" folder)
uv run --with pyshp --with pyproj python dbt_merge.py "<DBT 2020 - SHAPE dir>" milan-osm.json milan.json
# 2. tram routes and piazzas from Overpass (out geom), within 830 m of 45.4662, 9.1868
python3 -I add_trams.py trams.json milan.json      # relation["route"="tram"]
python3 -I add_piazzas.py squares.json milan.json  # highway=pedestrian / area:highway=pedestrian / place=square
# 3. sun hours
python3 -I sun_hours.py milan.json . 2026-06-21 2026-12-21 2026-03-20
```
`milan-osm.json` is the OSM snapshot of 2026-07-15 compacted by `prep.py`.

Built with Claude Code.
