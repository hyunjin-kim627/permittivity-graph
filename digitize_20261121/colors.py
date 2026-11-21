from PIL import Image
import numpy as np
import colorsys

p = r"C:\Users\user\OneDrive\문서\유전율_그래프_측정\새 폴더\10.1016_j.jeurceramsoc.2023.01.027_fig5.png"
a = np.array(Image.open(p).convert("RGB")).astype(int)
regions = {
    "a": (112, 302, 28, 193),
    "a_legend": (200, 300, 28, 90),
}
for name, (x0, x1, y0, y1) in regions.items():
    sub = a[y0:y1, x0:x1]
    mx = sub.max(axis=2)
    mn = sub.min(axis=2)
    sat = mx - mn
    mask = (sat > 45) & (mx > 90)
    px = sub[mask]
    print(name, "colored px", len(px))
    bins = {}
    for r, g, b in px[::5]:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        key = int(h * 12) % 12
        bins.setdefault(key, []).append((r, g, b, h * 360, v))
    for key in sorted(bins, key=lambda k: -len(bins[k]))[:10]:
        arr = np.array(bins[key])
        print(f"  huebin {key:2d} n={len(arr):5d} meanRGB={arr[:, :3].mean(axis=0).round(0)} hue={arr[:, 3].mean():.0f} V={arr[:, 4].mean():.2f}")
