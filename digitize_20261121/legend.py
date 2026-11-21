from PIL import Image
import numpy as np
import colorsys

p = r"C:\Users\user\OneDrive\문서\유전율_그래프_측정\새 폴더\10.1016_j.jeurceramsoc.2023.01.027_fig5.png"
a = np.array(Image.open(p).convert("RGB")).astype(int)
x0, x1, y0, y1 = 190, 305, 28, 92
sub = a[y0:y1, x0:x1]
mx, mn = sub.max(axis=2), sub.min(axis=2)
mask = (mx - mn > 45) & (mx > 90)
ys, xs = np.nonzero(mask)
for y, x in zip(ys, xs):
    r, g, b = sub[y, x]
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    if s > 0.25:
        print(f"x={x + x0:3d} y={y + y0:3d} hue={h * 360:5.0f} rgb=({r},{g},{b})")
