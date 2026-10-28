# Add pedestrian piazzas missing from data.areas: highway=pedestrian multipolygons, area:highway=pedestrian, and the
# fully pedestrian place=square outlines (named below: other "squares" in OSM include their roads).
# usage: python3 -I add_piazzas.py <overpass json (out geom)> <milan.json in/out>
import json, math, sys

LAT0, LON0, R = 45.4662, 9.1868, 800.0
KX = math.radians(1) * 6378137 * math.cos(math.radians(LAT0)); KY = math.radians(1) * 6378137  # same as prep.py
proj = lambda p: (round((p['lon'] - LON0) * KX, 1), round((p['lat'] - LAT0) * KY, 1))
SQUARES = {'Piazza del Duomo', 'Piazza dei Mercanti'}
CIRCLE = [(R * math.cos(a * math.pi / 96), R * math.sin(a * math.pi / 96)) for a in range(192)]

def clip(poly):  # Sutherland-Hodgman against the convex disc (as in prep.py)
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

def rings(members):  # join outer member ways into closed rings by matching endpoints (as in prep.py)
    segs = [[proj(p) for p in m['geometry']] for m in members if m.get('role') == 'outer' and m.get('geometry')]
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
            else: break
        if ring[0] == ring[-1] and len(ring) > 3: out.append(ring[:-1])
    return out

raw = json.load(open(sys.argv[1]))
d = json.load(open(sys.argv[2]))
cent = lambda f: (sum(f[0::2]) / len(f[0::2]), sum(f[1::2]) / len(f[1::2]))
have = [cent(a) for a in d['areas']]
added = []
for e in raw['elements']:
    t = e.get('tags', {})
    ped = t.get('highway') == 'pedestrian' or t.get('area:highway') == 'pedestrian'
    if not (ped or t.get('name') in SQUARES): continue
    polys = rings(e['members']) if e['type'] == 'relation' else ([[proj(p) for p in e['geometry']][:-1]] if e['geometry'][0] == e['geometry'][-1] else [])
    for p in polys:
        c = clip(p)
        if len(c) < 3: continue
        f = [int(round(v * 10)) for pt in c for v in pt]
        if any(math.hypot(cent(f)[0] - x, cent(f)[1] - y) < 20 for x, y in have): continue  # already there (dm)
        d['areas'].append(f); have.append(cent(f)); added.append(t.get('name', '-'))
json.dump(d, open(sys.argv[2], 'w'), separators=(',', ':'), ensure_ascii=False)
print('added', len(added), 'piazzas/pedestrian areas:', sorted(set(added)))
assert len(clip([(0, 0), (10, 0), (10, 10)])) == 3
