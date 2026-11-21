import sys
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, r"C:\Users\user\OneDrive\문서\유전율_그래프_측정")
from permittivity_digitizer import load_rgb, hsv_arrays

p = r"C:\Users\user\OneDrive\문서\유전율_그래프_측정\새 폴더\10.1016_j.jeurceramsoc.2023.01.027_fig5.png"
im, rgb = load_rgb(p)
R, G, B = im[..., 0], im[..., 1], im[..., 2]
H, S, V = hsv_arrays(rgb)
ns = {"R": R, "G": G, "B": B, "H": H, "S": S, "V": V}
plot = np.zeros(im.shape[:2], bool)
plot[454:610, 399:592] = True
rules = {
    "teal": "(B > 100) & (G > 95) & (R < 100) & (B > R + 40) & (G > R + 25) & (V >= 90) & (V < 190)",
    "cyan": "(B > 200) & (G > 180) & (R < 180) & (B > R + 50) & (V >= 190)",
}
for name, rule in rules.items():
    m = eval(rule, {}, ns) & plot
    lab, n = ndi.label(m, structure=np.ones((3, 3)))
    sizes = ndi.sum(m, lab, range(1, n + 1))
    order = np.argsort(sizes)[::-1][:8]
    print(name, "pixels", int(m.sum()), "components", n)
    for i in order:
        idx = i + 1
        ys, xs = np.nonzero(lab == idx)
        print("  size", int(sizes[i]), "x", int(xs.min()), int(xs.max()), "y", int(ys.min()), int(ys.max()))
