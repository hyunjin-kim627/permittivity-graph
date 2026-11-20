"""
Digitize a permittivity-vs-temperature plot from a PNG screenshot.

Method
  1. Calibrate axes (tick marks found automatically, or explicit pixel<->value
     points given in the config file).
  2. Extract each curve by colour (RGB/HSV rule strings in the config file).
  3. Per curve: peak (eps, T), eps at room temperature, min eps in a T range.
  4. Propagate a pixel-reading uncertainty -> relative error; values whose
     relative error exceeds rel_limit are reported as "읽기불가" (unreadable).
  5. Draw an overlay image so the detection can be checked by eye.

Usage
  python -I read_permittivity_plot.py IMAGE.png [--config CONFIG.json] [--outdir DIR]

  default config : config_ba_sr.json    (Ba1-xSrx)(Zr0.1Ti0.9)O3 figure, x = 0 .. 0.45
  other config   : config_dielectric_x1000.json   (30-110 C figure, x = 0 .. 0.09)

Needs: numpy, Pillow, scipy.

Config keys (JSON)
  x_axis / y_axis : {"auto_ticks": [values...]}            tick marks detected in the image
                    {"points": [[pixel, value], ...]}      explicit calibration (>= 2 points)
  plot_box        : [row0, row1, col0, col1]  region searched for curves (optional with auto_ticks)
  ignore          : [[row0, row1, col0, col1], ...]  regions to skip (legend, inset)
  room_T, T_range : room temperature, and T window for the min value
  sigma_px        : 1-sigma pixel reading error (an ASSUMPTION; includes calibration error)
  mark_half_px    : marker radius / half line width, px (edge pixel -> centre)
  smooth_window   : median window (columns) applied to the curve top before taking the peak
  rel_limit       : relative error above which a value is "unreadable"
  curves          : [{"name", "rule", "color", "min_component_px", "rows", "cols"}]
                    rule = python expression on arrays R,G,B (0-255), H (0-360), S (0-1), V (0-255)
                    (rules are evaluated with eval(): only use config files you wrote or trust)
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw


# ------------------------------------------------------------------ image I/O
def load(path):
    """Return (rgb int array, PIL RGB image). Transparent pixels are put on white."""
    rgba = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    bg.alpha_composite(rgba)
    rgb = bg.convert("RGB")
    return np.array(rgb).astype(int), rgb


def hsv_arrays(rgb_img):
    hsv = np.array(rgb_img.convert("HSV")).astype(float)
    return hsv[..., 0] * 360.0 / 255.0, hsv[..., 1] / 255.0, hsv[..., 2]


# --------------------------------------------------------------- axis finding
def find_axes(im):
    """Auto mode: pixel positions of x ticks (cols) and y ticks (rows) + axis lines."""
    gray = im.sum(axis=2) / 3
    dark = gray < 160
    rows = dark.sum(axis=1)
    cols = dark.sum(axis=0)
    bottom = [r for r in range(im.shape[0]) if rows[r] > 200][-2:]
    cl = [c for c in range(im.shape[1]) if cols[c] > 150]
    left, right = cl[0], cl[-1]
    y_axis_row = sum(bottom) / len(bottom)
    below = dark[int(max(bottom)) + 1:int(max(bottom)) + 6, :]
    xt = [c for c in range(left - 2, right + 3) if below[:, c].sum() >= 3]
    groups = []
    for c in xt:
        if not groups or c - groups[-1][-1] > 1:
            groups.append([c])
        else:
            groups[-1].append(c)
    x_cols = [float(np.mean(g)) for g in groups]
    leftof = dark[:, left - 7:left]
    yt = [r for r in range(im.shape[0]) if leftof[r, :].sum() >= 4 and r < min(bottom) - 5]
    return x_cols, yt, y_axis_row, left, right


def axis_fit(spec, auto_pixels, kind):
    """Return (a, b) with value = a*pixel + b."""
    if "points" in spec:
        px = [p[0] for p in spec["points"]]
        val = [p[1] for p in spec["points"]]
    else:
        vals = list(spec["auto_ticks"])
        if kind == "y":                    # rows grow downward, values upward
            px = sorted(auto_pixels)
            val = sorted(vals, reverse=True)
        else:
            px = auto_pixels
            val = vals
        if len(px) != len(val):
            raise SystemExit(f"{kind}-axis: found {len(px)} ticks {px}, expected {len(val)}")
    a, b = np.polyfit(px, val, 1)
    return a, b


# ----------------------------------------------------------- curve extraction
def class_mask(cfg_curve, ns, plot_mask):
    m = eval(cfg_curve["rule"], {"np": np}, ns) & plot_mask
    if "rows" in cfg_curve:
        r0, r1 = cfg_curve["rows"]
        keep = np.zeros_like(m)
        keep[r0:r1, :] = True
        m &= keep
    if "cols" in cfg_curve:
        c0, c1 = cfg_curve["cols"]
        keep = np.zeros_like(m)
        keep[:, c0:c1] = True
        m &= keep
    for a0, a1, b0, b1 in cfg_curve.get("ignore", []):     # per-curve exclusion (e.g. axis tick marks)
        m[a0:a1, b0:b1] = False
    n_min = cfg_curve.get("min_component_px", 0)
    if n_min:
        from scipy import ndimage as ndi
        lab, n = ndi.label(m, structure=np.ones((3, 3)))
        sizes = ndi.sum(m, lab, range(1, n + 1))
        for i, s in enumerate(sizes, start=1):
            if s < n_min:
                m[lab == i] = False
    return m


def envelope(mask, col0, col1):
    """Per column: (top_row, median_row, bottom_row) of the class pixels."""
    env = {}
    for c in range(col0, col1 + 1):
        rr = np.nonzero(mask[:, c])[0]
        if len(rr):
            env[c] = (float(rr.min()), float(np.median(rr)), float(rr.max()))
    return env


def smoothed_tops(env, w):
    cols = sorted(env)
    tops = {c: env[c][0] for c in cols}
    if w <= 1:
        return tops
    half = w // 2
    out = {}
    for c in cols:
        vals = [env[k][0] for k in range(c - half, c + half + 1) if k in env]
        out[c] = float(np.median(vals))
    return out


# ----------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?", default="permittivity.png")
    ap.add_argument("--config", default=None)
    ap.add_argument("--outdir", default=None, help="where results/overlay are written (default: next to the image)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    here = os.path.dirname(os.path.abspath(__file__))
    cfg_path = args.config or os.path.join(here, "config_ba_sr.json")
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    stem = os.path.splitext(os.path.basename(args.image))[0]
    outdir = args.outdir or os.path.dirname(os.path.abspath(args.image))
    os.makedirs(outdir, exist_ok=True)

    im, rgb_img = load(args.image)
    H_, W_, _ = im.shape
    R, G, B = im[..., 0], im[..., 1], im[..., 2]
    Hh, Ss, Vv = hsv_arrays(rgb_img)
    ns = {"R": R, "G": G, "B": B, "H": Hh, "S": Ss, "V": Vv}

    # ---- calibration
    auto = "auto_ticks" in cfg["x_axis"] or "auto_ticks" in cfg["y_axis"]
    if auto:
        x_cols, yt, y_axis_row, left, right = find_axes(im)
        y_pix = list(yt) + [y_axis_row]
    else:
        x_cols, y_pix = None, None
    ax, bx = axis_fit(cfg["x_axis"], x_cols, "x")
    ay, by = axis_fit(cfg["y_axis"], y_pix, "y")
    T = lambda c: ax * c + bx
    E = lambda r: ay * r + by
    col_of = lambda t: (t - bx) / ax
    deg_per_px, eps_per_px = abs(ax), abs(ay)

    if "plot_box" in cfg:
        r0, r1, c0, c1 = cfg["plot_box"]
    else:
        r0, r1, c0, c1 = 14, int(y_axis_row) - 2, left + 3, right - 1
    plot = np.zeros((H_, W_), bool)
    plot[r0:r1, c0:c1] = True
    for a0, a1, b0, b1 in cfg.get("ignore", []):
        plot[a0:a1, b0:b1] = False

    sigma = cfg.get("sigma_px", 1.5)
    half = cfg.get("mark_half_px", 1.5)
    rel_limit = cfg.get("rel_limit", 0.10)
    room_T = cfg.get("room_T", 25.0)
    Tlo_req, Thi_req = cfg.get("T_range", [-50.0, 150.0])
    win = cfg.get("smooth_window", 1)
    T_vis = sorted([T(c0), T(c1)])
    Tlo, Thi = max(Tlo_req, T_vis[0]), min(Thi_req, T_vis[1])

    lines = []
    out = lines.append
    out(f"image  : {args.image}")
    out(f"config : {cfg_path}")
    out(f"calibration: {deg_per_px:.3f} C/px, {eps_per_px:.1f} eps/px; sigma = {sigma} px "
        f"-> +-{sigma * deg_per_px:.2f} C, +-{sigma * eps_per_px:.0f} eps")
    out(f"visible T range in the figure: {T_vis[0]:.1f} .. {T_vis[1]:.1f} C")
    if (Tlo, Thi) != (Tlo_req, Thi_req):
        out(f"NOTE: requested min/max window {Tlo_req}..{Thi_req} C is wider than the figure; "
            f"using {Tlo:.1f}..{Thi:.1f} C")
    edge_tol = 3 * deg_per_px          # the search box stops ~3 px inside the frame; allow reading right at the edge
    room_ok = T_vis[0] - edge_tol <= room_T <= T_vis[1] + edge_tol
    if room_ok and not (T_vis[0] <= room_T <= T_vis[1]):
        out(f"NOTE: {room_T:g} C lies at the very edge of the figure; read from the nearest curve pixels "
            f"(offset added to the error)")
    if not room_ok:
        out(f"NOTE: room temperature {room_T} C is outside the plotted range -> cannot be read")

    def fmt(val, err):
        rel = err / abs(val) if val else float("inf")
        tag = "OK" if rel <= rel_limit else "읽기불가"
        return f"{val:8.0f} +-{err:5.0f} ({rel * 100:4.1f}%) {tag}"

    out("")
    out(f"{'curve':16s} | {'peak eps':32s} | {'peak T (C)':16s} | {'eps @%gC' % room_T:32s} | "
        f"{'min eps (%.0f..%.0fC)' % (Tlo, Thi):32s}")

    overlay = rgb_img.resize((W_ * 3, H_ * 3), Image.NEAREST)
    d = ImageDraw.Draw(overlay)
    d.rectangle([c0 * 3, r0 * 3, c1 * 3, r1 * 3], outline=(170, 170, 170))
    for a0, a1, b0, b1 in cfg.get("ignore", []):
        d.rectangle([b0 * 3, a0 * 3, b1 * 3, a1 * 3], outline=(200, 160, 160))

    results = []
    refs = []
    for cv in cfg["curves"]:
        name = cv["name"]
        m = class_mask(cv, ns, plot)
        if not m.any():
            out(f"{name:16s} | no pixels found")
            continue
        env = envelope(m, c0, c1 - 1)
        cols = sorted(env)
        tops = smoothed_tops(env, win)
        # ---- peak: highest (smoothed) top pixel, + half width -> centre
        top_row = min(tops.values())
        pk_cols = [c for c in cols if tops[c] <= top_row + 1]
        pk_col = float(np.mean(pk_cols))
        pk_eps = E(top_row + half)
        pk_T = T(pk_col)
        pk_err = sigma * eps_per_px
        pk_T_err = max(sigma, (max(pk_cols) - min(pk_cols)) / 2) * deg_per_px
        # ---- eps at room temperature
        if room_ok:
            c25 = col_of(room_T)
            c_use = min(max(c25, c0 + 2), c1 - 3)          # clamp to the searchable area
            offset_px = abs(c_use - c25)
            near = [c for c in cols if abs(c - c_use) <= 1.5]
            if near:
                r25 = float(np.mean([env[c][1] for c in near]))
                loc = [c for c in cols if abs(c - c_use) <= 4]
                slope_px = 0.0                                 # |d eps| per column
                if len(loc) >= 3:
                    k = np.polyfit(loc, [env[c][1] for c in loc], 1)[0]
                    slope_px = abs(k) * eps_per_px
                e25 = E(r25)
                e25_err = float(np.hypot(sigma * eps_per_px, slope_px * (sigma + offset_px)))
                s25 = fmt(e25, e25_err)
            else:
                s25 = "n/a"
        else:
            s25 = "범위 밖"
        # ---- min eps in the T window
        cwin = sorted([col_of(Tlo), col_of(Thi)])
        cr = [c for c in cols if cwin[0] <= c <= cwin[1]]
        if cr:
            bot_row = max(env[c][2] for c in cr)
            mn = E(bot_row - half)
            gaps = [b - a for a, b in zip(cr, cr[1:])]
            if min(cr) > cwin[0] + 4 or max(cr) < cwin[1] - 4 or (gaps and max(gaps) > 6):
                # curve not found over the whole window -> its true minimum may lie outside what was detected
                smin = f"n/a (곡선이 구간 전체에서 검출 안 됨: T={T(min(cr)):.0f}~{T(max(cr)):.0f}C) 읽기불가"
            elif bot_row >= r1 - 2:    # curve runs into the lower axis/search-box edge
                smin = f"<={mn:7.0f} (축 하단에 닿음) 읽기불가"
            else:
                smin = fmt(mn, sigma * eps_per_px)
        else:
            mn, smin = None, "n/a"
        # reference value at the visible edge nearest to room temperature (only when room T is out of range)
        if not room_ok:
            t_ref_col = c0 + 3 if abs(T(c0) - room_T) < abs(T(c1) - room_T) else c1 - 4
            nr = [c for c in cols if abs(c - t_ref_col) <= 1.5]
            if nr:
                rr_ = float(np.mean([env[c][1] for c in nr]))
                refs.append((name, T(t_ref_col), E(rr_)))
        out(f"{name:16s} | {fmt(pk_eps, pk_err):32s} | {pk_T:6.1f} +-{pk_T_err:4.1f}    | {s25:32s} | {smin:32s}")
        results.append((name, pk_eps, pk_T))

        # overlay: curve centre line, peak cross + label
        col = tuple(cv.get("color", [0, 0, 0]))
        for c in cols:
            d.point((c * 3 + 1, env[c][1] * 3 + 1), fill=col)
        x, y = pk_col * 3 + 1, (top_row + half) * 3 + 1
        d.line([(x - 7, y), (x + 7, y)], fill=(0, 190, 0), width=1)
        d.line([(x, y - 7), (x, y + 7)], fill=(0, 190, 0), width=1)
        d.text((x + 9, y - 6), f"{pk_eps:.0f} @ {pk_T:.1f}C", fill=col)

    if room_ok:
        x25 = col_of(room_T) * 3 + 1
        d.line([(x25, r0 * 3), (x25, r1 * 3)], fill=(150, 150, 150), width=1)

    # ---- overall (all curves together) max / min inside the window
    if results:
        n_best = max(results, key=lambda t: t[1])
        out("")
        out(f"전체 최대(모든 곡선 중): {fmt(n_best[1], sigma * eps_per_px)} at T={n_best[2]:.1f} C  [{n_best[0]}]")
        anyline = ((Ss > 0.25) | (Vv < 140)) & plot
        cw = sorted([int(col_of(Tlo)), int(col_of(Thi))])
        edge_cols = list(range(cw[1] - 6, cw[1] + 1))      # right end: all curves converge here
        rows_ = [r for c in edge_cols for r in np.nonzero(anyline[:, c])[0]]
        if rows_:
            bot = max(rows_)
            mn_all = E(bot - half)
            if bot >= r1 - 2:
                out(f"전체 최소(모든 곡선 중): <={mn_all:.0f} (축 하단에 닿음) 읽기불가")
            else:
                out(f"전체 최소(모든 곡선 중): {fmt(mn_all, sigma * eps_per_px)} at T~{T(edge_cols[-1]):.0f} C "
                    f"(곡선들이 겹쳐 어느 조성인지는 구분 불가)")
    if refs:
        out(f"참고: 상온({room_T:g} C)이 범위 밖이라, 그래프 가장자리(T={refs[0][1]:.1f} C)에서 읽은 값 "
            f"(상온 값이 아님, 가장자리는 곡선이 흔들려 오차가 더 클 수 있음)")
        for n_, t_, e_ in refs:
            out(f"   {n_:16s} eps({t_:.1f} C) = {e_:8.0f} +-{sigma * eps_per_px:5.0f}")
    res_path = os.path.join(outdir, f"{stem}_results.txt")
    ov_path = os.path.join(outdir, f"{stem}_overlay.png")
    out("")
    out(f"overlay: {ov_path}  (green cross + label = detected peak; gray box = search area; "
        f"pink boxes = ignored areas; dots = detected curve centre)")
    text = "\n".join(lines)
    print(text)
    with open(res_path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    overlay.save(ov_path)


if __name__ == "__main__":
    main()
