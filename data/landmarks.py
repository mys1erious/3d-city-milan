# Landmark fixes OSM's tags can't express: the Galleria Vittorio Emanuele II's covered streets are open below their glass
# vaults, the Ottagono's glass dome sits on the crossing, and the entrance arch on Piazza del Duomo has an attic above it.
# Dimensions: A. Rondello, as published by Politecnico di Milano, re.public.polimi.it/bitstream/11311/1006962/1/GVE%20volume%20OS%202016.pdf
# (arms 14.5 m wide, vault springing 25.07 m, crown 29.28 m; Ottagono dome springing 20.15 m, top 47.08 m; arch 27.8 m to the
# keystone, attic top 38.5 m). The building in front of each arm's outer end gets a passage cut through it (the arch on
# Piazza del Duomo: 12 m wide, open to 27.8 m, attic to 38.5 m; the other entrances: the arm's width, open to the vault).
# The arms and the Ottagono floor are added as pedestrian areas so people walk through them.
# Also: Palazzo della Ragione's arcade and the Vittorio Emanuele II monument (sources below).
# usage: python3 -I landmarks.py milan.json   (after dbt_merge.py, add_trams.py, add_piazzas.py)
import json, sys

d = json.load(open(sys.argv[1])); N = d['names']
GAL, OTT = N.index('Galleria Vittorio Emanuele Secondo'), N.index('Ottagono')
bbox = lambda f: (min(f[0::2]), max(f[0::2]), min(f[1::2]), max(f[1::2]))
arms = [b for b in d['b'] if b[2] == GAL]
assert len(arms) == 4, len(arms)
for b in arms:
    hs = b[5] if len(b) > 5 else []
    b[:] = [29.28, 25.07, GAL, 0, b[4], hs, 3, 4.21]  # barrel vault: springing 25.07 m, crown 29.28 m
for b in d['b']:
    if b[2] == OTT: b[:] = [47.08, 20.15, OTT, 0, b[4], b[5] if len(b) > 5 else [], 2, 26.93]  # glass dome on the crossing
if 'Arco della Galleria' in N: sys.exit('already applied: run on a fresh milan.json (dbt_merge.py, add_trams.py, add_piazzas.py first)')
N.append('Arco della Galleria'); ARCO = N.index('Arco della Galleria')

def half(poly, axis, v, less):  # Sutherland-Hodgman against one axis-aligned half-plane (works for non-convex rings too)
    pts = [(poly[i], poly[i + 1]) for i in range(0, len(poly), 2)]; out = []
    inn = lambda p: (p[axis] <= v) if less else (p[axis] >= v)
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        if inn(p): out.append(p)
        if inn(p) != inn(q):
            t = (v - p[axis]) / (q[axis] - p[axis]); out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return [int(round(c)) for pt in out for c in pt] if len(out) >= 3 else None
inside = lambda x, y, f: sum(1 for i in range(0, len(f), 2) if ((f[i + 1] > y) != (f[i - 1] > y)) and x < (f[i - 2] - f[i]) * (y - f[i + 1]) / (f[i - 1] - f[i + 1]) + f[i]) % 2 == 1

# cut each arm's entrance through the building in front of its outer end (dm units, x east / y north)
oc = [b for b in d['b'] if b[2] == OTT][0][4]; ox, oy = sum(oc[0::2]) / len(oc[0::2]), sum(oc[1::2]) / len(oc[1::2])
cut = []
for arm in arms:
    x0, x1, y0, y1 = bbox(arm[4]); ns = (x1 - x0) < (y1 - y0)  # north-south arm?
    if ns:
        c = (x0 + x1) / 2; end = y0 if abs(y0 - oy) > abs(y1 - oy) else y1; out = -1 if end == y0 else 1; ax = 0
    else:
        c = (y0 + y1) / 2; end = x0 if abs(x0 - ox) > abs(x1 - ox) else x1; out = -1 if end == x0 else 1; ax = 1
    duomo_side = ns and out == -1 and end == min(bbox(a[4])[2] for a in arms)
    hw = 60 if duomo_side else (x1 - x0 if ns else y1 - y0) / 2  # the main arch is 12 m wide; the others the arm's width
    top = 278 if duomo_side else 250  # open to the keystone (27.8 m) / to the vault springing
    probe = [(c, end + out * k) if ns else (end + out * k, c) for k in (20, 60, 100, 140)]  # 2..14 m out from the arm
    cut.append((ax, c - hw, c + hw, top / 10, duomo_side, probe))

new_b, new_g, passages = [], [], []
for b, g in zip(d['b'], d['grp']):
    hit = next((k for k in cut if any(inside(px, py, b[4]) for px, py in k[5])), None)
    if not hit or b[2] in (GAL, OTT): new_b.append(b); new_g.append(g); continue
    ax, lo, hi, top, main, _ = hit
    for piece in (half(b[4], ax, lo, True), half(b[4], ax, hi, False)):  # the building either side of the passage
        if piece: new_b.append([b[0], b[1], b[2], b[3], piece]); new_g.append(g)
    mid = half(half(b[4], ax, lo, False) or [], ax, hi, True) if half(b[4], ax, lo, False) else None
    if mid: passages.append(mid); new_b.append([38.5 if main else b[0], top, ARCO if main else b[2], 0 if main else b[3], mid]); new_g.append(-1 if main else g)  # over the arch
d['b'], d['grp'] = new_b, new_g
import math
# Palazzo della Ragione (Broletto Nuovo) stands on an open arcade: 7 arches on each long side, 2 on each short side
# (it.wikipedia.org/wiki/Palazzo_della_Ragione_(Milano)). No published height found: the hall is lifted to 8 m, an estimate.
RAG = N.index('Palazzo della Ragione')
rag = [b for b in d['b'] if b[2] == RAG]
assert len(rag) == 1
f = rag[0][4]; pts = [(f[i] / 10, f[i + 1] / 10) for i in range(0, len(f), 2)]
cx, cy = sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts)
sxx = sum((x - cx) ** 2 for x, _ in pts); syy = sum((y - cy) ** 2 for _, y in pts); sxy = sum((x - cx) * (y - cy) for x, y in pts)
th = 0.5 * math.atan2(2 * sxy, sxx - syy); ux, uy = math.cos(th), math.sin(th)  # long axis of the footprint
us = [(x - cx) * ux + (y - cy) * uy for x, y in pts]; vs = [-(x - cx) * uy + (y - cy) * ux for x, y in pts]
u0, u1, v0, v1 = min(us) + 0.7, max(us) - 0.7, min(vs) + 0.7, max(vs) - 0.7  # pillar centres, 0.7 m in from the walls
P = lambda u, v: (cx + u * ux - v * uy, cy + u * uy + v * ux)
spots = {(round(u0 + (u1 - u0) * i / 7, 2), round(v, 2)) for i in range(8) for v in (v0, v1)} | {(round(u, 2), round(v0 + (v1 - v0) * j / 2, 2)) for j in range(3) for u in (u0, u1)}  # corners once
rag[0][1] = 8.0
for u, v in spots:
    sq = [P(u - 0.7, v - 0.7), P(u + 0.7, v - 0.7), P(u + 0.7, v + 0.7), P(u - 0.7, v + 0.7)]
    d['b'].append([8.0, 0, RAG, 3, [int(round(c * 10)) for p in sq for c in p]]); d['grp'].append(d['grp'][d['b'].index(rag[0])])

# Monument to Vittorio Emanuele II (Ercole Rosa, 1896): 14.8 m with its base, at 45.464200 N, 9.189239 E
# (it.wikipedia.org/wiki/Monumento_a_Vittorio_Emanuele_II_(Milano)). Footprint estimated: base 7 x 11 m, rider 2.4 x 5.5 m.
LAT0, LON0 = 45.4662, 9.1868
mx = (9.189239 - LON0) * math.radians(1) * 6378137 * math.cos(math.radians(LAT0)); my = (45.464200 - LAT0) * math.radians(1) * 6378137
if 'Monumento a Vittorio Emanuele II' not in N: N.append('Monumento a Vittorio Emanuele II')
MON = N.index('Monumento a Vittorio Emanuele II')
box = lambda hx, hy: [int(round(c * 10)) for p in ((mx - hx, my - hy), (mx + hx, my - hy), (mx + hx, my + hy), (mx - hx, my + hy)) for c in p]
d['b'] += [[8.5, 0, MON, 0, box(5.5, 3.5)], [14.8, 8.5, MON, 0, box(2.75, 1.2)]]; d['grp'] += [-1, -1]  # the rider faces the Duomo (east)

# OSM stacks tower stages as parts with min_height; where a stage starts above the one under it (the Filarete tower has
# gaps at 40-45, 50-53 and 60-64 m) it would float, so each kept OSM part is extended down to the top of what is under it
ctr = lambda f: (sum(f[0::2]) / len(f[0::2]), sum(f[1::2]) / len(f[1::2]))
for b in d['b']:
    if b[3] == 0 and b[1] > 0 and b[2] not in (GAL, OTT, ARCO, MON):
        cx, cy = ctr(b[4])
        under = [o[0] for o in d['b'] if o is not b and o[0] <= b[1] + 0.01 and inside(cx, cy, o[4])]
        if under and max(under) < b[1] - 0.05: b[1] = round(max(under), 2)

floors = [b[4] for b in arms] + [b[4] for b in d['b'] if b[2] == OTT] + passages
d['areas'] = [a for a in d['areas'] if a not in floors] + floors
json.dump(d, open(sys.argv[1], 'w'), separators=(',', ':'), ensure_ascii=False)
print('Galleria arms', len(arms), '· Ottagono', sum(b[2] == OTT for b in d['b']), '· entrances cut', len(cut), '· arch pieces', sum(b[2] == ARCO for b in d['b']),
      '· Ragione pillars', len(spots), '· monument at', round(mx, 1), round(my, 1))
assert len(d['grp']) == len(d['b'])
