# Compact the raw Overpass dump into data/milan.json: local metres (decimetre ints), clipped to a disc.
# usage: python3 -I prep.py raw.json out.json
import json, math, statistics, sys

LAT0, LON0, R = 45.4662, 9.1868, 800.0
KX = math.radians(1) * 6378137 * math.cos(math.radians(LAT0)); KY = math.radians(1) * 6378137
proj = lambda p: (round((p['lon'] - LON0) * KX, 1), round((p['lat'] - LAT0) * KY, 1))
CIRCLE = [(R * math.cos(a * math.pi / 96), R * math.sin(a * math.pi / 96)) for a in range(192)]  # CCW, convex

def clip(poly):  # Sutherland-Hodgman against the convex disc polygon
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

def area(p): return 0.5 * sum(p[i][0] * p[i - 1][1] - p[i - 1][0] * p[i][1] for i in range(len(p)))
def centroid(p): return (sum(x for x, _ in p) / len(p), sum(y for _, y in p) / len(p))
def inside(pt, poly):
    x, y, c = pt[0], pt[1], False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c

def rings(members, role):  # join member ways into closed rings by matching endpoints
    segs = [[proj(p) for p in m['geometry']] for m in members if m.get('role') == role and m.get('geometry')]
    out = []
    while segs:
        ring = segs.pop(0)
        while ring[0] != ring[-1]:
            for k, s in enumerate(segs):
                if s[0] == ring[-1]: ring += s[1:]
                elif s[-1] == ring[-1]: ring += s[::-1][1:]
                elif s[-1] == ring[0]: ring = s + ring[1:]
                elif s[0] == ring[0]: ring = s[::-1] + ring[1:]
                else: continue
                segs.pop(k); break
            else: break  # open ring: give up on it
        if ring[0] == ring[-1] and len(ring) > 3: out.append(ring[:-1])
    return out

def polys(e):  # -> list of (outer, holes)
    if e['type'] == 'way':
        g = [proj(p) for p in e['geometry']]
        return [(g[:-1], [])] if len(g) > 3 and g[0] == g[-1] else []
    outs, inns = rings(e['members'], 'outer'), rings(e['members'], 'inner')
    return [(o, [h for h in inns if inside(h[0], o)]) for o in outs]

def num(v):
    try: return float(str(v).replace(',', '.').replace('m', '').strip())
    except ValueError: return None

def flat(p): return [int(round(c * 10)) for pt in p for c in pt]

raw = json.load(open(sys.argv[1]))
E = raw['elements']
B, P, ROADS, AREAS, GREEN = [], [], [], [], []
for e in E:
    t = e.get('tags', {})
    if 'building' in t or 'building:part' in t:
        for o, hs in polys(e):
            (P if 'building:part' in t and 'building' not in t else B).append((e, o, hs))
    elif t.get('leisure') == 'park' or t.get('landuse') == 'grass':
        GREEN += [o for o, _ in polys(e)]
    elif 'highway' in t:
        g = [proj(p) for p in e['geometry']]
        if t.get('area') == 'yes' and t['highway'] in ('pedestrian', 'footway'):
            AREAS.append(g[:-1])
        else:
            w = {'trunk': 16, 'primary': 15, 'secondary': 13, 'tertiary': 11, 'residential': 8, 'unclassified': 8,
                 'living_street': 7, 'pedestrian': 7}.get(t['highway'])
            if w and t.get('tunnel') not in ('yes', 'building_passage'): ROADS.append((w, g))

lv_h = [num(e[0]['tags']['building:levels']) * 3.2 for e in B if num(e[0]['tags'].get('building:levels')) ]
DEFAULT_H = round(statistics.median(lv_h), 1)
SMALL = {'roof': 4, 'kiosk': 3, 'shed': 3, 'hut': 3, 'garage': 3, 'garages': 3, 'toilets': 3, 'cabin': 3, 'carport': 3}

def heights(t):
    h, src = num(t.get('height')), 0
    if h is None and num(t.get('building:levels')) is not None:
        h, src = num(t['building:levels']) * 3.2, 1
    if h is None:
        h, src = SMALL.get(t.get('building'), DEFAULT_H), 2
    mh = num(t.get('min_height'))
    if mh is None: mh = num(t.get('building:min_level')) * 3.2 if num(t.get('building:min_level')) else 0
    if t.get('building') == 'roof' and not mh: mh = max(0, h - 1)
    return h, min(mh, h - 0.5), src

names, nidx = [], {}
def name_id(n):
    if not n: return -1
    if n not in nidx: nidx[n] = len(names); names.append(n)
    return nidx[n]

ROOF = {'pyramidal': 1, 'cone': 1, 'dome': 2, 'onion': 2, 'round': 2, 'gabled': 3, 'hipped': 3, 'half-hipped': 3, 'gambrel': 3, 'mansard': 3}
out_b = []
part_cent = [centroid(o) for _, o, _ in P]
outline_of_part = [None] * len(P)
for e, o, hs in B:
    owns = [i for i, c in enumerate(part_cent) if inside(c, o)]
    for i in owns: outline_of_part[i] = outline_of_part[i] or e['tags'].get('name')
    if owns: continue  # 3D convention: parts replace their outline
    out_b.append((e['tags'], o, hs, e['tags'].get('name')))
for i, (e, o, hs) in enumerate(P):
    out_b.append((e['tags'], o, hs, e['tags'].get('name') or outline_of_part[i]))

res_b, stats = [], [0, 0, 0]
for t, o, hs, n in out_b:
    if any(math.hypot(*p) > R for p in o): o = clip(o); hs = [clip(h) for h in hs]
    if len(o) < 3 or abs(area(o)) < 2: continue
    h, mh, src = heights(t)
    if h <= 0.2: continue
    rs = ROOF.get(t.get('roof:shape'), 0); rh = num(t.get('roof:height'))
    rec = [round(h, 1), round(mh, 1), name_id(n), src, flat(o)]
    hs = [flat(x) for x in hs if len(x) >= 3 and abs(area(x)) > 1]
    if hs or rs: rec.append(hs)
    if rs: rec += [rs, round(rh, 1) if rh is not None else -1]
    res_b.append(rec); stats[src] += 1

def clip_line(g):  # split a polyline into runs inside the disc
    runs, cur = [], []
    for i, p in enumerate(g):
        ins = math.hypot(*p) <= R
        if i and ins != (math.hypot(*g[i - 1]) <= R):
            a, b = g[i - 1], p; lo, hi = 0.0, 1.0  # bisect the crossing point
            for _ in range(30):
                m = (lo + hi) / 2; q = (a[0] + (b[0] - a[0]) * m, a[1] + (b[1] - a[1]) * m)
                if (math.hypot(*q) <= R) == (math.hypot(*a) <= R): lo = m
                else: hi = m
            cur.append(q)
            if not ins: runs.append(cur); cur = []
        if ins: cur.append(p)
    if cur: runs.append(cur)
    return [r for r in runs if len(r) >= 2]

roads = [[w, flat(r)] for w, g in ROADS for r in clip_line(g)]
areas = [flat(c) for a in AREAS for c in [clip(a)] if len(c) >= 3]
green = [flat(c) for a in GREEN for c in [clip(a)] if len(c) >= 3]
data = {'attribution': '© OpenStreetMap contributors (ODbL)', 'osm_base': raw.get('osm3s', {}).get('timestamp_osm_base'),
        'center': [LAT0, LON0], 'radius': R, 'unit': 'dm, x east / y north', 'default_height': DEFAULT_H,
        'format': 'b: [height m, min_height m, name index, source 0 height/1 levels/2 default, outer ring, holes?, roof shape 1 pyr/2 dome/3 gable, roof height]',
        'names': names, 'b': res_b, 'roads': roads, 'areas': areas, 'green': green}
json.dump(data, open(sys.argv[2], 'w'), separators=(',', ':'), ensure_ascii=False)
print('buildings', len(res_b), 'by source height/levels/default', stats, 'parts', len(P), 'default', DEFAULT_H,
      'roads', len(roads), 'areas', len(areas), 'green', len(green), 'names', len(names))
assert clip([(0, 0), (10, 0), (10, 10)]) and math.hypot(*clip([(700, 0), (900, 0), (900, 50)])[1]) <= R + 1e-6
