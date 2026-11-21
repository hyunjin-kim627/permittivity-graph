from PIL import Image
import numpy as np

p = r"C:\Users\user\OneDrive\문서\유전율_그래프_측정\새 폴더\10.1016_j.jeurceramsoc.2023.01.027_fig5.png"
a = np.array(Image.open(p).convert("L")).astype(int)
dark = a < 160
bands = [(26, 193), (243, 405), (452, 615)]

def runs(idx, gap=3):
    if not len(idx):
        return []
    parts = np.split(idx, np.nonzero(np.diff(idx) > gap)[0] + 1)
    return [(int(q[0]), int(q[-1]), int(len(q))) for q in parts]

for y0, y1 in bands:
    h = y1 - y0 + 1
    c = dark[y0:y1 + 1].sum(axis=0)
    print("BAND", y0, y1, "threshold", int(h * 0.65))
    print("  vertical", runs(np.nonzero(c >= h * 0.65)[0]))
    for x0, x1, _ in runs(np.nonzero(c >= h * 0.65)[0]):
        r = dark[:, x0:x1 + 1].sum(axis=1)
        print("   x", x0, x1, "horizontal", runs(np.nonzero(r >= (x1 - x0 + 1) * 0.6)[0]))
