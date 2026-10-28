# Minutes of direct sun at street level (1 m above the ground) for every 2 m cell of the disc, from building shadows only
# (trees are not counted; buildings outside the 800 m disc are missing, so cells near the edge get too much low sun).
# Writes data/sun-<date>.png: grey = minutes / 5, alpha 0 under buildings and outside the disc.
# usage: python3 -I sun_hours.py milan.json out_dir 2026-06-21 2026-12-21 ...
import json, math, sys, datetime
import numpy as np
from PIL import Image, ImageDraw

RES, Z0, STEP_MIN = 2.0, 1.0, 5
LAT, LON = 45.464, 9.190  # same point as the page's sun

def sun(ms):  # NOAA solar position, same formulas as the page (alt with refraction, az from north)
    RAD = math.pi / 180
    jd = ms / 864e5 + 2440587.5; T = (jd - 2451545) / 36525
    L0 = (280.46646 + T * (36000.76983 + T * 0.0003032)) % 360
    M = 357.52911 + T * (35999.05029 - 0.0001537 * T)
    e = 0.016708634 - T * (0.000042037 + 0.0000001267 * T)
    C = math.sin(M * RAD) * (1.914602 - T * (0.004817 + 0.000014 * T)) + math.sin(2 * M * RAD) * (0.019993 - 0.000101 * T) + math.sin(3 * M * RAD) * 0.000289
    om = 125.04 - 1934.136 * T
    lam = L0 + C - 0.00569 - 0.00478 * math.sin(om * RAD)
    eps = 23 + (26 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60) / 60 + 0.00256 * math.cos(om * RAD)
    decl = math.asin(math.sin(eps * RAD) * math.sin(lam * RAD))
    y = math.tan(eps * RAD / 2) ** 2
    eot = 4 / RAD * (y * math.sin(2 * L0 * RAD) - 2 * e * math.sin(M * RAD) + 4 * e * y * math.sin(M * RAD) * math.cos(2 * L0 * RAD)
                     - 0.5 * y * y * math.sin(4 * L0 * RAD) - 1.25 * e * e * math.sin(2 * M * RAD))
    utc = (ms % 864e5) / 6e4
    ha = ((utc + eot + 4 * LON) / 4 - 180) * RAD; la = LAT * RAD
    alt0 = math.asin(math.sin(la) * math.sin(decl) + math.cos(la) * math.cos(decl) * math.cos(ha)) / RAD
    az = (math.atan2(math.sin(ha), math.cos(ha) * math.sin(la) - math.tan(decl) * math.cos(la)) / RAD + 540) % 360
    te = math.tan(alt0 * RAD)
    refr = 0 if alt0 > 85 else (58.1 / te - 0.07 / te ** 3 + 0.000086 / te ** 5) if alt0 > 5 else \
        (1735 + alt0 * (-518.2 + alt0 * (103.4 + alt0 * (-12.79 + alt0 * 0.711)))) if alt0 > -0.575 else -20.774 / te
    return alt0 + refr / 3600, az

ms = lambda iso: datetime.datetime.fromisoformat(iso).replace(tzinfo=datetime.timezone.utc).timestamp() * 1000
assert abs(sun(ms('2026-06-21T11:25:00'))[0] - 67.98) < 0.05 and abs(sun(ms('2026-10-28T11:06:00'))[0] - 31.36) < 0.05  # matches the page

d = json.load(open(sys.argv[1])); R = d['radius']; N = int(2 * R / RES)
H = np.zeros((N, N), np.float32)  # row 0 = south edge; H[iy, ix] at x = (ix + .5) * RES - R, y = (iy + .5) * RES - R
for b in d['b']:
    pts = lambda f: [((f[i] / 10 + R) / RES, (f[i + 1] / 10 + R) / RES) for i in range(0, len(f), 2)]
    o = pts(b[4]); xs, ys = [p[0] for p in o], [p[1] for p in o]
    x0, y0 = max(int(min(xs)) - 1, 0), max(int(min(ys)) - 1, 0); x1, y1 = min(int(max(xs)) + 2, N), min(int(max(ys)) + 2, N)
    if x1 <= x0 or y1 <= y0: continue
    img = Image.new('L', (x1 - x0, y1 - y0), 0); dr = ImageDraw.Draw(img)
    sh = lambda p: [(x - x0 - 0.5, y - y0 - 0.5) for x, y in p]  # pixel centres
    dr.polygon(sh(o), fill=1)
    for h in (b[5] if len(b) > 5 else []): dr.polygon(sh(pts(h)), fill=0)
    m = np.asarray(img, bool)
    H[y0:y1, x0:x1][m] = np.maximum(H[y0:y1, x0:x1][m], b[0])
yy, xx = np.mgrid[0:N, 0:N]; inside = np.hypot((xx + .5) * RES - R, (yy + .5) * RES - R) <= R
ground = inside & (H == 0)
HMAX = float(H.max())
Hp = np.pad(H, N)  # zero border so shifts never wrap

def lit(alt, az):
    t = math.tan(math.radians(alt)); sx, sy = math.sin(math.radians(az)), math.cos(math.radians(az))
    shade = np.zeros((N, N), bool); dmax = min((HMAX - Z0) / t, 2 * R)
    for k in range(1, int(dmax / RES) + 1):
        dist = k * RES; ox, oy = int(round(dist * sx / RES)), int(round(dist * sy / RES))
        shade |= Hp[N + oy:2 * N + oy, N + ox:2 * N + ox] > Z0 + dist * t
    return ~shade

out_dir = sys.argv[2]
for date in sys.argv[3:]:
    total = np.zeros((N, N), np.float32); day = 0
    t0 = ms(date + 'T00:00:00') - 3 * 3600e3  # covers Rome's day in UTC
    for k in range(0, 30 * 60, STEP_MIN):
        alt, az = sun(t0 + k * 6e4)
        if alt <= 0: continue
        day += STEP_MIN; total += lit(alt, az) * STEP_MIN
    img = np.zeros((N, N, 2), np.uint8)
    img[..., 0] = np.clip(np.round(total / 5), 0, 255); img[..., 1] = ground * 255
    Image.fromarray(img[::-1], 'LA').save(f'{out_dir}/sun-{date}.png')  # PNG row 0 = north
    g = total[ground]
    print(date, f'day {day / 60:.2f} h; street cells median {np.median(g) / 60:.1f} h, p10 {np.percentile(g, 10) / 60:.1f} h, p90 {np.percentile(g, 90) / 60:.1f} h')
    probe = lambda x, y: total[int((y + R) / RES), int((x + R) / RES)] / 60
    print('  Piazza del Duomo (250, -224):', round(probe(250, -224), 2), 'h')
