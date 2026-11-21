from PIL import Image
import numpy as np

p = r"C:\Users\user\OneDrive\문서\유전율_그래프_측정\새 폴더\10.1016_j.jeurceramsoc.2023.01.027_fig5.png"
a = np.array(Image.open(p).convert("RGB")).astype(int)
regions = {
    "a": (205, 232, 28, 82),
    "b": (465, 492, 28, 82),
    "c": (765, 792, 28, 82),
    "d": (222, 248, 248, 298),
    "e": (492, 518, 248, 298),
    "f": (208, 234, 458, 508),
    "g": (538, 564, 458, 530),
}
for name, (x0, x1, y0, y1) in regions.items():
    sub = a[y0:y1, x0:x1]
    mx, mn = sub.max(axis=2), sub.min(axis=2)
    colored = (mx - mn > 40) & (mx > 80)
    counts = colored.sum(axis=1)
    rows = np.nonzero(counts >= 8)[0]
    groups = np.split(rows, np.nonzero(np.diff(rows) > 2)[0] + 1) if len(rows) else []
    print(name)
    for g in groups:
        y = int(g.mean()) + y0
        px = sub[g][colored[g]]
        if len(px):
            print(f"   y={y:3d} n={len(px):3d} rgb={px.mean(axis=0).round(0)}")
