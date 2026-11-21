import sys
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, r"C:\Users\user\OneDrive\문서\유전율_그래프_측정")
from permittivity_digitizer import load_rgb, hsv_arrays

p = r"C:\Users\user\OneDrive\문서\유전율_그래프_측정\새 폴더\10.1016_j.jeurceramsoc.2023.01.027_fig5.png"
im, rgb = load_rgb(p)
R, G, B = im[..., 0], im[..., 1], im[..., 2]
H, S, V = hsv_arrays(rgb)
plot = np.zeros(im.shape[:2], bool)
plot[29:192, 112:302] = True
ns = {"R": R, "G": G, "B": B, "H": H, "S": S, "V": V}
for rule in ["(V < 95) & (S < 0.35)", "(V < 140) & (S < 0.35)", "(V < 180) & (S < 0.35)"]:
    m = eval(rule, {}, ns) & plot
    lab, n = ndi.label(m, structure=np.ones((3, 3)))
    sizes = sorted(ndi.sum(m, lab, range(1, n + 1)), reverse=True)[:12]
    print(rule, "pixels", int(m.sum()), "components", n, "top sizes", [int(s) for s in sizes])
    for size in sizes[:5]:
        idx = np.nonzero(ndi.sum(m, lab, range(1, n + 1)) == size)[0][0] + 1
        ys, xs = np.nonzero(lab == idx)
        print("   size", int(size), "x", int(xs.min()), int(xs.max()), "y", int(ys.min()), int(ys.max()))
