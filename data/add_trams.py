# Add the real tram lines (OSM route=tram relations, one per direction) to milan.json as paths inside the disc.
# usage: python3 -I add_trams.py <overpass relations json (out geom)> <milan.json in/out>
import json, math, sys

LAT0, LON0, R = 45.4662, 9.1868, 800.0
KX = math.radians(1) * 6378137 * math.cos(math.radians(LAT0)); KY = math.radians(1) * 6378137  # same as prep.py
proj = lambda p: ((p['lon'] - LON0) * KX, (p['lat'] - LAT0) * KY)
dist = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])

def chain(ways):  # member ways are listed in travel order; flip each one to continue from the previous end
    path = list(ways[0]) if ways else []
    for k, g in enumerate(ways[1:]):
        near = lambda p: min(dist(g[0], p), dist(g[-1], p))
        if k == 0 and near(path[0]) < near(path[-1]): path.reverse()  # the first way was stored backwards
        if dist(g[-1], path[-1]) < dist(g[0], path[-1]): g = g[::-1]
        if dist(g[0], path[-1]) > 30: path += [None] + list(g)  # gap: start a new run
        else: path += g[1:]
    return path

def runs_inside(path):  # split at gaps and at the disc edge; keep runs over 150 m
    out, cur = [], []
    for p in path + [None]:
        if p is None or math.hypot(*p) > R:
            if len(cur) >= 2 and sum(dist(cur[i], cur[i + 1]) for i in range(len(cur) - 1)) > 150: out.append(cur)
            cur = []
        else: cur.append(p)
    return out

raw = json.load(open(sys.argv[1])); rels = raw['elements']
d = json.load(open(sys.argv[2]))
trams = []
for r in rels:
    ways = [[proj(p) for p in m['geometry']] for m in r['members']
            if m['type'] == 'way' and m.get('role', '') in ('', 'forward', 'backward') and m.get('geometry')]
    for run in runs_inside(chain(ways)):
        trams.append([r['tags'].get('ref', ''), [int(round(c * 10)) for p in run for c in p]])
d['trams'] = trams
d['tram_base'] = raw.get('osm3s', {}).get('timestamp_osm_base')
json.dump(d, open(sys.argv[2], 'w'), separators=(',', ':'), ensure_ascii=False)
km = sum(math.hypot(t[1][i + 2] - t[1][i], t[1][i + 3] - t[1][i + 1]) for t in trams for i in range(0, len(t[1]) - 2, 2)) / 1e4
print('tram runs', len(trams), 'lines', sorted({t[0] for t in trams}, key=lambda s: (len(s), s)), f'{km:.1f} km')
assert runs_inside([(0, 0), (100, 0), (200, 0), None, (0, 1)]) == [[(0, 0), (100, 0), (200, 0)]]
