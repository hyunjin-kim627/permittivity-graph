"""Guide-assisted curve tracing for black-and-white plots.
Each curve = list of segments. A segment has a guide polyline given in DISPLAY coordinates of the
k-times enlarged crop (X, Y), a mode ('x': step over columns, 'y': step over rows) and a half-width W
(original px). For every column (or row) the dark run closest to the guide is taken."""
import sys; sys.path.insert(0, '.')
import numpy as np
from PIL import Image
from calib import fits

def load(p):
    a = Image.open(p).convert('RGBA'); bg = Image.new('RGBA', a.size, (255,255,255,255)); bg.alpha_composite(a)
    return np.array(bg.convert('L')).astype(int)

def runs(v, merge=2):
    idx = np.nonzero(v)[0]
    if not len(idx): return []
    sp = np.split(idx, np.nonzero(np.diff(idx) > merge + 1)[0] + 1)
    return [(s[0], s[-1]) for s in sp]

def trace(name, curve, k=3, thr=150):
    c = fits(name); t, b, l, r = c['box']
    d = load(c['file']) < thr
    for (r0, r1, c0, c1) in curve.get('ignore', []):
        d[r0:r1, c0:c1] = False
    pts = []
    for seg in curve['segments']:
        G = np.array(seg['guide'], float)
        gc = (l - 2) + G[:, 0] / k; gr = (t - 2) + G[:, 1] / k     # guide in original px
        W = seg.get('W', 4)
        if seg['mode'] == 'x':
            o = np.argsort(gc); gc, gr = gc[o], gr[o]
            for col in range(int(np.ceil(gc[0])), int(np.floor(gc[-1])) + 1):
                g = np.interp(col, gc, gr)
                lo, hi = int(g - W), int(g + W) + 1
                rr = [(a + lo, z + lo) for a, z in runs(d[lo:hi, col])]
                rr = [x for x in rr if x[1] - x[0] <= 9]
                if rr:
                    a, z = min(rr, key=lambda x: abs((x[0] + x[1]) / 2 - g))
                    pts.append((col, (a + z) / 2, seg['mode']))
        else:
            o = np.argsort(gr); gc, gr = gc[o], gr[o]
            for row in range(int(np.ceil(gr[0])), int(np.floor(gr[-1])) + 1):
                g = np.interp(row, gr, gc)
                lo, hi = int(g - W), int(g + W) + 1
                cc = [(a + lo, z + lo) for a, z in runs(d[row, lo:hi])]
                cc = [x for x in cc if x[1] - x[0] <= 9]
                if cc:
                    a, z = min(cc, key=lambda x: abs((x[0] + x[1]) / 2 - g))
                    pts.append(((a + z) / 2, row, seg['mode']))
    out = [(c['ax'] * x + c['bx'], (c['ay'] * y + c['by']) * 1000, x, y, m) for x, y, m in pts]
    return c, out
