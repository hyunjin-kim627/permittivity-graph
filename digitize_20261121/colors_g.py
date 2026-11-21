from PIL import Image
import numpy as np
import colorsys

p = r"C:\Users\user\OneDrive\문서\유전율_그래프_측정\새 폴더\10.1016_j.jeurceramsoc.2023.01.027_fig5.png"
a = np.array(Image.open(p).convert("RGB")).astype(int)
sub = a[454:613, 398:594]
mx, mn = sub.max(axis=2), sub.min(axis=2)
mask = (mx - mn > 35) & (mx > 70)
px = sub[mask]
print("colored", len(px))
bins = {}
for r, g, b in px[::3]:
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    key = (int(h * 24) % 24, int(v * 5))
    bins.setdefault(key, []).append((r, g, b, h * 360, v))
for key in sorted(bins, key=lambda k: -len(bins[k]))[:20]:
    arr = np.array(bins[key])
    print(f"huebin {key[0]*15:3d}-{key[0]*15+15:3d} Vbin {key[1]} n={len(arr):5d} rgb={arr[:, :3].mean(axis=0).round(0)} hue={arr[:, 3].mean():.0f} V={arr[:, 4].mean():.2f}")
