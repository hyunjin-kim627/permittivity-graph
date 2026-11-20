"""
Digitize the (Ba1-xSrx)(Zr0.1Ti0.9)O3 permittivity-vs-temperature plot
(axis range 30..110 C, eps x1000 10..40) -- adapted from
read_permittivity_plot.py for "화면 캡처 test.png".

Axis calibration was measured from the tick labels (OCR + pixel positions):
  X ticks : 30..110 C  at cols 54.1 .. 323.1
  Y ticks : 10..40 (x1000) at rows 36.3 .. 180.8
Curves are separated by hue (legend handle colours).

Usage:  python read_permittivity_plot_adapted.py permittivity.png
"""
import sys
import numpy as np
from PIL import Image, ImageDraw

REL_LIMIT = 0.10
SIGMA_PX = 1.5
MARKER_HALF = 1.5

X_TICK_COLS = [54.1, 87.75, 121.6, 154.9, 188.75, 222.6, 255.75, 289.75, 323.1]
X_TICK_VALS = [30, 40, 50, 60, 70, 80, 90, 100, 110]
Y_TICK_ROWS = [36.3, 59.9, 84.7, 108.6, 132.7, 156.7, 180.8]
Y_TICK_VALS = [40000, 35000, 30000, 25000, 20000, 15000, 10000]

ROOM_T = 25.0
T_MIN, T_MAX = -50.0, 150.0

PLOT = dict(top=19, bottom=218, left=56, right=323)
LEGEND = (56, 112, 25, 95)          # col0, col1, row0, row1

HUE_CENTERS = {
    "x=0.01 (red)":    0.010,
    "x=0.03 (blue)":   0.673,
    "x=0.05 (teal)":   0.482,
    "x=0.07 (purple)": 0.816,
    "x=0.09 (olive)":  0.186,
}
HUE_TOL = 0.045


def load(path):
    return np.array(Image.open(path).convert("RGB")).astype(float) / 255.0


def rgb_to_hsv(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    df = mx - mn
    h = np.zeros_like(mx)
    m = df > 1e-9
    idx = m & (mx == r)
    h[idx] = ((g[idx] - b[idx]) / df[idx]) % 6
    idx = m & (mx == g)
    h[idx] = (b[idx] - r[idx]) / df[idx] + 2
    idx = m & (mx == b)
    h[idx] = (r[idx] - g[idx]) / df[idx] + 4
    h = (h / 6.0) % 1.0
    s = np.where(mx > 0, df / np.where(mx == 0, 1, mx), 0)
    return h, s, mx


def main(path):
    sys.stdout.reconfigure(encoding="utf-8")
    im = load(path)
    H, W, _ = im.shape
    h, s, v = rgb_to_hsv(im)

    ax, bx = np.polyfit(X_TICK_COLS, X_TICK_VALS, 1)
    ay, by = np.polyfit(Y_TICK_ROWS, Y_TICK_VALS, 1)
    T = lambda c: ax * c + bx
    E = lambda r: ay * r + by
    col_of = lambda t: (t - bx) / ax
    deg_per_px, eps_per_px = abs(ax), abs(ay)
    print(f"calibration: {deg_per_px:.3f} C/px, {eps_per_px:.1f} eps/px; "
          f"sigma = {SIGMA_PX} px -> +-{SIGMA_PX*deg_per_px:.1f} C, +-{SIGMA_PX*eps_per_px:.0f} eps")

    reg = np.zeros((H, W), bool)
    reg[PLOT["top"]:PLOT["bottom"], PLOT["left"]:PLOT["right"]] = True
    c0, c1, r0, r1 = LEGEND
    reg[r0:r1, c0:c1] = False

    overlay = Image.open(path).convert("RGB").resize((W * 3, H * 3), Image.NEAREST)
    d = ImageDraw.Draw(overlay)

    def fmt(val, err):
        rel = err / abs(val) if val else float("inf")
        tag = "OK" if rel <= REL_LIMIT else "읽기불가"
        return f"{val:8.0f} +-{err:5.0f} ({rel*100:4.1f}%) {tag}"

    print(f"\n{'curve':16s} | {'peak eps':32s} | {'peak T (C)':16s} | {'eps @30C':32s} | "
          f"{'max eps (data)':16s} | {'min eps (data)':32s}")
    for name, hc in HUE_CENTERS.items():
        dist = np.abs(h - hc)
        dist = np.minimum(dist, 1 - dist)
        m = (dist < HUE_TOL) & (s > 0.2) & (v > 0.2) & reg
        env = {}
        for c in range(PLOT["left"], PLOT["right"] + 1):
            rr = np.nonzero(m[:, c])[0]
            if len(rr):
                env[c] = (rr.min(), float(np.median(rr)), rr.max())
        cols = sorted(env)
        if not cols:
            print(f"{name:16s} | no pixels")
            continue
        top_row = min(env[c][0] for c in cols)
        pk_cols = [c for c in cols if env[c][0] <= top_row + 1]
        pk_col = float(np.mean(pk_cols))
        pk_eps = E(top_row + MARKER_HALF)
        pk_T = T(pk_col)
        pk_err = SIGMA_PX * eps_per_px
        pk_T_err = max(SIGMA_PX, (max(pk_cols) - min(pk_cols)) / 2) * deg_per_px

        t_lo = max(T_MIN, T(cols[0]))
        t_hi = min(T_MAX, T(cols[-1]))
        e25 = "n/a (X축 30-110C)"
        for tt, tol in ((ROOM_T, 1.5), (30.0, 3.0)):
            c25 = col_of(tt)
            near = [c for c in cols if abs(c - c25) <= tol]
            if near:
                r25 = float(np.mean([env[c][1] for c in near]))
                e25 = fmt(E(r25), float(np.hypot(SIGMA_PX * eps_per_px, 0.0)))
                if tt == ROOM_T:
                    e25 = "n/a(축밖)"
                else:
                    e25 = "30C: " + e25
                break

        cr = [c for c in cols if col_of(t_lo) <= c <= col_of(t_hi)]
        mx_eps = E(min(env[c][0] for c in cr) + MARKER_HALF)
        bot_row = max(env[c][2] for c in cr)
        mn_eps = E(bot_row - MARKER_HALF)
        smin = fmt(mn_eps, SIGMA_PX * eps_per_px)
        print(f"{name:16s} | {fmt(pk_eps, pk_err):32s} | {pk_T:6.1f} +-{pk_T_err:4.1f}    | "
              f"{e25:32s} | {mx_eps:16.0f} | {smin:32s}")

        for c in cols:
            d.point((c * 3 + 1, env[c][1] * 3 + 1), fill=(0, 0, 0))
        x, y = pk_col * 3 + 1, (top_row + MARKER_HALF) * 3 + 1
        d.line([(x - 6, y), (x + 6, y)], fill=(0, 200, 0), width=1)
        d.line([(x, y - 6), (x, y + 6)], fill=(0, 200, 0), width=1)

    for tt, colr in ((ROOM_T, (150, 150, 150)), (30.0, (120, 120, 255))):
        x = col_of(tt) * 3 + 1
        d.line([(x, 0), (x, H * 3)], fill=colr, width=1)
    out = path.rsplit(".", 1)[0] + "_overlay.png"
    overlay.save(out)
    print(f"\noverlay saved: {out}  (green cross = peak, gray = 25 C(out of axis), blue = 30 C)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "permittivity.png")
