# Replace OSM building footprints/heights with the Comune di Milano DBT 2020 survey volumes (UN_VOL, CC-BY 4.0).
# Keeps OSM for the Duomo (its spire parts + Madonnina) and every OSM shape with a roof shape (domes, pyramids, gables).
# usage: uv run --with pyshp --with pyproj python dbt_merge.py <dbt shp dir> <milan.json in> <milan.json out>
import json, math, statistics, sys, collections
import shapefile
from pyproj import Transformer

D, SRC, OUT = sys.argv[1:4]
LAT0, LON0, R = 45.4662, 9.1868, 800.0
KX = math.radians(1) * 6378137 * math.cos(math.radians(LAT0)); KY = math.radians(1) * 6378137  # same as prep.py
T = Transformer.from_crs(7791, 4326, always_xy=True)
x0, y0 = Transformer.from_crs(4326, 7791, always_xy=True).transform(LON0, LAT0)
CIRCLE = [(R * math.cos(a * math.pi / 96), R * math.sin(a * math.pi / 96)) for a in range(192)]

def loc(x, y):
    lon, lat = T.transform(x, y); return ((lon - LON0) * KX, (lat - LAT0) * KY)
def area(p): return 0.5 * sum(p[i - 1][0] * p[i][1] - p[i][0] * p[i - 1][1] for i in range(len(p)))  # >0 = CCW
def centroid(p):
    a = area(p)
    if abs(a) < 1e-9: return (sum(x for x, _ in p) / len(p), sum(y for _, y in p) / len(p))
    cx = sum((p[i - 1][0] + p[i][0]) * (p[i - 1][0] * p[i][1] - p[i][0] * p[i - 1][1]) for i in range(len(p)))
    cy = sum((p[i - 1][1] + p[i][1]) * (p[i - 1][0] * p[i][1] - p[i][0] * p[i - 1][1]) for i in range(len(p)))
    return (cx / (6 * a), cy / (6 * a))
def inside(pt, poly):
    x, y, c = pt[0], pt[1], False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c
def clip(poly):  # Sutherland-Hodgman against the convex disc (copied from prep.py)
    out = poly
    for i in range(len(CIRCLE)):
        (ax, ay), (bx, by) = CIRCLE[i], CIRCLE[(i + 1) % len(CIRCLE)]
        side = lambda p: (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)
        src, out = out, []
        for j in range(len(src)):
            p, q = src[j], src[(j + 1) % len(src)]
            sp, sq = side(p), side(q)
            if sp >= 0: out.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq); out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
        if not out: return []
    return out
def flat(p): return [int(round(c * 10)) for pt in p for c in pt]
def unflat(f): return [(f[i] / 10, f[i + 1] / 10) for i in range(0, len(f), 2)]
def bbox(p): xs, ys = [x for x, _ in p], [y for _, y in p]; return (min(xs), min(ys), max(xs), max(ys))

def hit(pt, shapes):
    return [s for s in shapes if s[2][0] <= pt[0] <= s[2][2] and s[2][1] <= pt[1] <= s[2][3] and inside(pt, s[1])]

osm = json.load(open(SRC))
names = osm['names']
duomo_ids = {i for i, n in enumerate(names) if n.startswith('Duomo di Milano')}
oidx = {id(b): i for i, b in enumerate(osm['b'])}
keep, outlines = [], []  # OSM records kept as-is; named OSM outlines for name lookup
for b in osm['b']:
    ring = unflat(b[4])
    if (b[2] in duomo_ids and b[0] > 95) or (b[2] not in duomo_ids and len(b) > 6): keep.append((b, ring, bbox(ring)))  # OSM: Duomo spire tip + Madonnina, roof forms
    outlines.append((b, ring, bbox(ring)))
# a kept part that floats (min_height > 0, e.g. a tower's roof) needs the OSM shapes under it too, or it hovers over the lower DBT eave
for b, ring, bb in list(keep):
    if b[1] > 0 and b[2] not in duomo_ids:
        c = centroid(ring)
        keep += [s for s in outlines if s[0] is not b and all(s[0] is not k[0] for k in keep) and s[0][1] < b[1] and hit(c, [s])]
print('OSM kept:', len(keep), 'of', len(osm['b']), '(Duomo parts', sum(k[0][2] in duomo_ids for k in keep), ')')


# read volumes near the disc, rings in local metres
vols = []
for sr in shapefile.Reader(f"{D}/UN_VOL").iterShapeRecords():
    bb = sr.shape.bbox
    if math.hypot((bb[0] + bb[2]) / 2 - x0, (bb[1] + bb[3]) / 2 - y0) > R + 120: continue
    pts, parts = sr.shape.points, list(sr.shape.parts) + [len(sr.shape.points)]
    rings = [[loc(*p) for p in pts[parts[i]:parts[i + 1]]] for i in range(len(parts) - 1)]
    rings = [r[:-1] if r[0] == r[-1] else r for r in rings]
    ced = sr.record['CEDIUV'] or ''
    vols.append((sr.record['UN_VOL_AV'], sr.record['UN_VOL_POR'], sr.shape.z[0], rings, int(ced.split('_')[-1]) if ced[-1:].isdigit() else -1))

# local ground level: median base z of ordinary ('01') volumes per 100 m cell
cells = collections.defaultdict(list)
for av, por, z, rings, _ in vols:
    if por == '01': c = centroid(rings[0]); cells[(int(c[0] // 100), int(c[1] // 100))].append(z)
gmed = statistics.median(z for v in cells.values() for z in v)
def ground(c):
    zs = [z for dx in (-1, 0, 1) for dy in (-1, 0, 1) for z in cells.get((int(c[0] // 100) + dx, int(c[1] // 100) + dy), [])]
    return statistics.median(zs) if len(zs) >= 5 else gmed

res, grp, ced_of, cmp, skipped = [], [], [], [], collections.Counter()
for av, por, z, rings, ged in vols:
    outers = [r for r in rings if area(r) < 0 and len(r) >= 3]  # shapefile outer rings are clockwise
    holes = [r for r in rings if area(r) > 0 and len(r) >= 3]
    if not outers: skipped['no outer'] += 1; continue
    if av < 1.0: skipped['under 1 m'] += 1; continue
    for o in outers:
        c = centroid(o)
        if math.hypot(*c) > R + 5 and all(math.hypot(*p) > R for p in o): continue
        if hit(c, [k for k in keep if k[0][2] not in duomo_ids]): skipped['inside kept OSM'] += 1; continue  # the Duomo's DBT volumes stay
        g = ground(c)
        mh = z - g if z - g > 1.5 else 0.0  # raised volumes (over porticoes, passages) start above the street
        top = mh + av
        oo = o[::-1]  # CCW like prep.py output
        hs = [h[::-1] for h in holes if inside(h[0], o)]
        if any(math.hypot(*p) > R for p in oo): oo = clip(oo); hs = [clip(h) for h in hs]
        if len(oo) < 3 or abs(area(oo)) < 2: continue
        n = hit(c, outlines)
        nid = next((s[0][2] for s in n if s[0][2] >= 0), -1)
        own = min(n, key=lambda s: abs(area(s[1])))[0] if n else None  # the OSM building (palazzo) this volume sits in
        for s in n:
            if s[0][3] == 0 and por == '01': cmp.append((top, s[0][0]))
        rec = [round(top, 1), round(mh, 1), nid, 3, flat(oo)]
        hs = [flat(h) for h in hs if len(h) >= 3 and abs(area(h)) > 1]
        if hs: rec.append(hs)
        res.append(rec); grp.append(oidx[id(own)] if own else 100000 + ged); ced_of.append(ged)

# an unnamed volume takes the name most volumes of its DBT building have (the Duomo's buttresses stick out of its OSM outline)
by_ced = collections.defaultdict(list)
for i, g in enumerate(ced_of): by_ced[g].append(i)
for g, ids in by_ced.items():
    names = collections.Counter(res[i][2] for i in ids if res[i][2] >= 0)
    if g >= 0 and names and names.most_common(1)[0][1] * 2 > len(ids):
        for i in ids:
            if res[i][2] < 0: res[i][2] = names.most_common(1)[0][0]
res += [k[0] for k in keep]; grp += [-1] * len(keep)
d = dict(osm)
d['attribution'] = '© OpenStreetMap contributors (ODbL) · Buildings: Comune di Milano, DBT 2020 (CC-BY 4.0)'
d['format'] = 'b: [height m, min_height m, name index, source 0 height/1 levels/2 default/3 DBT survey, outer ring, holes?, roof shape 1 pyr/2 dome/3 gable, roof height]'
d['b'] = res
d['grp'] = grp  # per entry of b: index of the OSM building it sits in (else 100000 + DBT EDIFC id), -1 for kept OSM shapes
# trees from DBT ALBERO points
trees = []
for sr in shapefile.Reader(f"{D}/ALBERO").iterShapes():
    x, y = sr.points[0]
    if math.hypot(x - x0, y - y0) <= R + 20:
        p = loc(x, y)
        if math.hypot(*p) <= R: trees += flat([p])
d['trees'] = trees
json.dump(d, open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)

diffs = sorted(abs(a - b) for a, b in cmp)
print('DBT volumes written', len(res) - len(keep), 'skipped', dict(skipped), 'ground median', round(gmed, 1))
print('trees', len(trees) // 2, 'named volumes', sum(r[2] >= 0 for r in res))
if diffs: print(f'check vs OSM height tags: n={len(diffs)} median |diff| {statistics.median(diffs):.1f} m, p90 {diffs[int(len(diffs)*.9)]:.1f} m')
tops = sorted(r[0] for r in res); print('top heights', tops[-8:])
assert area([(0, 0), (1, 0), (0, 1)]) > 0 and abs(centroid([(0, 0), (3, 0), (0, 3)])[0] - 1) < 1e-9 and inside((0.2, 0.2), [(0, 0), (1, 0), (0, 1)])
