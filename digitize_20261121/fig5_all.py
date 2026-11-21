import json
import os
import shutil
import subprocess
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

BASE = r"C:\Users\user\AppData\Local\Temp\opencode\digitize_20261121"
IMAGE = r"C:\Users\user\OneDrive\문서\유전율_그래프_측정\새 폴더\10.1016_j.jeurceramsoc.2023.01.027_fig5.png"
SCRIPT = r"C:\Users\user\OneDrive\문서\유전율_그래프_측정\permittivity_digitizer.py"

RULES = {
    "black": ("(V < 95) & (S < 0.35)", [0, 0, 0], 8),
    "red": ("(R > 150) & (G < 130) & (B < 130) & (R > G + 70)", [220, 60, 50], 60),
    "blue": ("(B > 140) & (B > R + 70) & (B > G + 60)", [20, 40, 200], 60),
    "magenta": ("(R > 150) & (B > 140) & (G < 170) & (R > G + 50) & (B > G + 40)", [220, 50, 200], 60),
    "teal": ("(B > 100) & (G > 95) & (R < 100) & (B > R + 40) & (G > R + 25) & (V >= 90) & (V < 180)", [60, 125, 142], 60),
    "cyan": ("(B > 150) & (G > 140) & (B > R + 50) & (G > R + 40) & (V >= 180) & (V < 260)", [120, 210, 235], 60),
}
FREQ = [("black", "1kHz (black)"), ("red", "10kHz (red)"), ("blue", "100kHz (blue)"), ("magenta", "1MHz (magenta)")]
COMP = [("black", "x=0 (black)"), ("red", "x=0.08 (red)"), ("blue", "x=0.1 (blue)"),
        ("teal", "x=0.12 (teal)"), ("cyan", "x=0.15 (cyan)"), ("magenta", "x=0.2 (magenta)")]

PANELS = [
    dict(key="a", box=[29, 192, 112, 302], x=[[111.5, -100], [144, -50], [176.5, 0], [208.5, 50], [240.5, 100], [272.5, 150], [305, 200]],
         y=[[27.5, 12000], [83, 8000], [110.5, 6000], [165.5, 2000]], legend=[205, 232, 28, 82], curves=FREQ),
    dict(key="b", box=[28, 192, 390, 582], x=[[426.5, 0], [466, 50], [505.5, 100], [545, 150], [584.5, 200]],
         y=[[27, 2700], [47, 2400], [68.5, 2100], [89, 1800], [110, 1500], [129.5, 1200], [151, 900], [171, 600], [192, 300]],
         legend=[465, 492, 28, 82], curves=FREQ),
    dict(key="c", box=[28, 192, 669, 862], x=[[665, -50], [705, 0], [745, 50], [785, 100], [825, 150], [865, 200]],
         y=[[27.5, 2400], [55.5, 2100], [83, 1800], [110.5, 1500], [137.5, 1200], [164.5, 900], [192, 600]],
         legend=[765, 792, 28, 82], curves=FREQ),
    dict(key="d", box=[245, 410, 108, 305], x=[[109, -50], [149, 0], [187.5, 50], [227.5, 100], [267.5, 150], [308, 200]],
         y=[[275.5, 1500], [309, 1200], [339.5, 900], [371.5, 600]], legend=[222, 248, 248, 298], curves=FREQ),
    dict(key="e", box=[245, 410, 388, 586], x=[[389.5, -50], [429.5, 0], [469.5, 50], [509.5, 100], [549, 150], [589, 200]],
         y=[[276, 1400], [308.5, 1200], [340.5, 1000], [373.5, 800], [405.5, 600]], legend=[492, 518, 248, 298], curves=FREQ),
    dict(key="f", box=[454, 613, 106, 304], x=[[107, -50], [147, 0], [187, 50], [227.5, 100], [267, 150], [306.5, 200]],
         y=[[454, 1600], [480, 1400], [507, 1200], [539, 1000], [560, 800], [585, 600], [612, 400]], legend=[208, 234, 458, 508], curves=FREQ),
    dict(key="g", box=[454, 610, 399, 592], x=[[400, -50], [439.5, 0], [477.5, 50], [517, 100], [556.5, 150], [595.5, 200]],
         y=[[453, 12000], [476.5, 10000], [499, 8000], [522, 6000], [568.5, 2000]], legend=[538, 564, 458, 530], curves=COMP),
]

wb = Workbook()
info = wb.active
info.title = "설명"
lines = [
    "원본: 10.1016_j.jeurceramsoc.2023.01.027_fig5.png (962x702)",
    "OCR(RapidOCR)로 축 눈금과 범례 위치를 읽어 패널별 설정을 자동 생성했습니다.",
    "읽은 패널: (a)~(g). (h)는 ln(1/eps-1/epsm) vs ln(T-Tm) 선형 피트라 제외했습니다.",
    "각 곡선은 색으로 구분했습니다. 검정(1kHz 또는 x=0)은 선이 가늘어 오차가 큽니다.",
    "(a) 패널 1kHz 피크 10379 @ -15.8 C: 논문 본문의 x=0, 1kHz εmax=10433 과 대체로 일치합니다.",
    "눈금 값/색 매핑은 OCR과 논문 캡션에 근거한 추정입니다. 반드시 overlay 이미지로 확인하세요.",
]
for line in lines:
    info.append([line])
info.column_dimensions["A"].width = 120

for panel in PANELS:
    key = panel["key"]
    r0, r1, c0, c1 = panel["box"]
    lx0, lx1, ly0, ly1 = panel["legend"]
    curves = []
    for color_key, name in panel["curves"]:
        rule, col, nmin = RULES[color_key]
        cv = {"name": name, "color": col, "rule": rule, "min_component_px": nmin}
        if key == "g":
            cv["rows"] = [455, 595]
            cv["cols"] = [399, 592]
            cv["ignore"] = [[458, 530, 530, 566]]
        elif color_key == "black":
            cv["rows"] = [ly1 - 40, r1]
            cv["cols"] = [c0, c1]
            cv["ignore"] = [[ly0, ly1 - 35, lx0 - 5, lx1 + 45]]
        curves.append(cv)
    cfg = {
        "name": f"Fig5({key}) OCR-generated",
        "x_axis": {"points": panel["x"]},
        "y_axis": {"points": panel["y"]},
        "plot_box": panel["box"],
        "ignore": [],
        "room_T": 25,
        "T_range": [-50, 200],
        "sigma_px": 1.5,
        "mark_half_px": 1.0,
        "smooth_window": 3,
        "rel_limit": 0.12,
        "curves": curves,
    }
    cfg_path = os.path.join(BASE, f"config_fig5_{key}.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    cmd = [sys.executable, SCRIPT, "color", IMAGE, "--config", cfg_path, "--outdir", BASE]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print("FAILED", key, proc.stderr[-500:])
        continue
    stem = os.path.splitext(os.path.basename(IMAGE))[0]
    overlay = os.path.join(BASE, f"{stem}_overlay.png")
    if os.path.exists(overlay):
        shutil.copy(overlay, os.path.join(BASE, f"fig5_overlay_{key}.png"))
    res = os.path.join(BASE, f"{stem}_results.xlsx")
    src = load_workbook(res, data_only=True)["결과"]
    ws = wb.create_sheet(f"Fig5({key})")
    for row in src.values:
        ws.append(list(row))
    for cell_ in ws[1]:
        cell_.font = Font(bold=True)
    ws.column_dimensions["A"].width = 22
    print("done", key, "rows", src.max_row)

out = os.path.join(BASE, "fig5_전체_결과.xlsx")
wb.save(out)
print("excel:", out)
