"""Axis calibration for the two black-and-white BaTiO3 figures (Arlt et al. style, grain-size study).
Pixel positions of tick marks were detected automatically (short inward ticks next to the frame)."""
import numpy as np
F2 = 'fig2_BaTiO3_3transitions.png'
F1 = 'fig1_BaTiO3_grainsize.png'
PANELS = {
    # name: (file, x ticks (px, value), y ticks (px, value), plot box (top, bottom, left, right))
    'fig1':  (F1, ([146.5,198.5,249.5,301.5,353.0,404.5], [-100,-50,0,50,100,150]),
                  ([52.5,92.5,133.5,174.5,214.5,255.5,296.5,336.5,377.5,418.0,459.0,499.5], list(range(12,0,-1))),
                  (31, 539, 96, 447)),
    'fig2a': (F2, ([158.0,217.5,277.0,336.5], [100,110,120,130]),
                  ([82.5,129.5,177.5,225.0,273.0,321.0,368.5,415.5,464.0,511.0], list(range(10,0,-1))),
                  (33, 558, 99, 396)),
    'fig2b': (F2, ([569.5,615.5,662.5,709.5,756.5], [-10,0,10,20,30]),
                  ([79.5,125.5,172.5,220.5,267.5], [5,4,3,2,1]),
                  (34, 314, 521, 802)),
    'fig2c': (F2, ([570.5,617.5,663.5,710.5,757.5,804.5], [-110,-100,-90,-80,-70,-60]),
                  ([416.5,464.5,511.0,557.5], [4,3,2,1]),
                  (369, 605, 523, 831)),
}
def fits(name):
    f, (xp, xv), (yp, yv), box = PANELS[name]
    ax, bx = np.polyfit(xp, xv, 1); ay, by = np.polyfit(yp, yv, 1)
    rx = np.std(np.array(xv) - (ax*np.array(xp)+bx)); ry = np.std(np.array(yv) - (ay*np.array(yp)+by))
    return dict(file=f, ax=ax, bx=bx, ay=ay, by=by, box=box, rx=rx, ry=ry)
if __name__ == '__main__':
    for n in PANELS:
        c = fits(n)
        print(f"{n}: {abs(c['ax']):.4f} C/px  {abs(c['ay'])*1000:.1f} eps/px   fit residual x {c['rx']:.3f} C, y {c['ry']*1000:.1f} eps")
