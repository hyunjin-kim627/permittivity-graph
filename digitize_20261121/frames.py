from PIL import Image
import numpy as np

p = r"C:\Users\user\OneDrive\문서\유전율_그래프_측정\새 폴더\10.1016_j.jeurceramsoc.2023.01.027_fig5.png"
a = np.array(Image.open(p).convert("L")).astype(int)
dark = a < 140
rows = dark.sum(axis=1)
cols = dark.sum(axis=0)

def groups(vals, thr):
    idx = np.nonzero(vals >= thr)[0]
    if not len(idx):
        return []
    out = []
    for part in np.split(idx, np.nonzero(np.diff(idx) > 2)[0] + 1):
        out.append((int(part[0]), int(part[-1]), int(vals[part].max())))
    return out

print("ROWS", groups(rows, 220))
print("COLS", groups(cols, 180))
for y0, y1, _ in groups(rows, 220):
    print("row band", y0, y1, "col groups", [g for g in groups(dark[y0:y1 + 1].sum(axis=0), max(20, (y1 - y0) // 2))])
