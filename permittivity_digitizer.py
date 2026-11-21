"""
permittivity_digitizer.py  --  one-file permittivity-vs-temperature plot digitizer

Two modes in one file:

  color : colour plots. Curves are separated by colour rules (RGB/HSV).
          Per curve: peak (eps, T), eps at room temperature, min eps in a T window, with errors.
          Writes <image>_results.txt and <image>_overlay.png (and <image>_results.xlsx).
  bw    : black-and-white plots. Curves cannot be told apart by colour, so each curve gets a rough
          guide path; the dark line pixels closest to the guide are traced column by column
          (row by row for near-vertical parts) and written to an Excel workbook (+ check images).

Usage
  python permittivity_digitizer.py color IMAGE.png [--preset ba_sr|x1000 | --config CONFIG.json] [--outdir DIR]
  python permittivity_digitizer.py bw [--config BW.json] [--images DIR] [--outdir DIR]
  python permittivity_digitizer.py ticks IMAGE.png [--box top,bottom,left,right ...] [--outdir DIR]
  python permittivity_digitizer.py presets [--outdir DIR]      # write the built-in presets as JSON templates

  ticks : step 1 for a NEW plot. Finds the rectangular plot frame(s) and the tick marks on each edge
          (ticks that lie on an evenly spaced grid; curves/labels touching the frame are rejected).
          Writes <image>_ticks.txt (pixel positions), <image>_ticks.png (frames + numbered ticks)
          and <image>_ticks.json = a bw config draft: write the axis value of every tick into
          x_ticks[1] / y_ticks[1], add the curves, then run `bw --config`.
          The tick pixels can also be used in a color config as "points": [[pixel, value], ...].
          If a frame is missed or wrong (e.g. a legend box, or axes without a closed frame), give it with --box.

  color without --preset/--config uses the built-in "ba_sr" preset.
  bw without --config runs the built-in BaTiO3 grain-size preset (Fig.1, Fig.2a-c);
     its images are looked up in --images (default: the bw_test folder next to this file).

Needs: numpy, Pillow, scipy (color mode, min_component_px only), openpyxl (Excel output).

---------------------------------------------------------------------------------------------
COLOR config keys (JSON)
  x_axis / y_axis : {"auto_ticks": [values...]}            tick marks detected in the image
                    {"points": [[pixel, value], ...]}      explicit calibration (>= 2 points)
  plot_box        : [row0, row1, col0, col1]  region searched for curves (optional with auto_ticks)
  ignore          : [[row0, row1, col0, col1], ...]  regions to skip (legend, inset)
  room_T, T_range : room temperature, and T window for the min value
  sigma_px        : 1-sigma pixel reading error (an ASSUMPTION; includes calibration error)
  mark_half_px    : marker radius / half line width, px (edge pixel -> centre)
  smooth_window   : median window (columns) applied to the curve top before taking the peak
  rel_limit       : relative error above which a value is "unreadable"
  curves          : [{"name", "rule", "color", "min_component_px", "rows", "cols", "ignore"}]
                    rule = python expression on arrays R,G,B (0-255), H (0-360), S (0-1), V (0-255)
                    (rules are evaluated with eval(): only use config files you wrote or trust)

BW config keys (JSON)
  excel           : output workbook name
  description     : list of text lines for the "설명" sheet (optional)
  notes           : {curve name: remark}  (optional, shown in the 비고 column)
  jobs            : list of panels, each
     sheet, title, file   : sheet name, chart title, image file (relative to --images)
     x_ticks, y_ticks     : [[pixels...], [values...]]  tick positions (px) and their values
     box                  : [top, bottom, left, right]  plot frame in px
     k                    : enlargement factor the guide coordinates refer to
     step                 : T step (C) of the output table
     y_scale              : factor applied to y values (default 1000: axis in units of 10^3)
     curves               : {name: {"ignore": [[row0,row1,col0,col1],...] (original px),
                                    "segments": [{"mode": "x"|"y", "W": half-width px,
                                                  "guide": [[X,Y],...]}]}}
                            guide = points in the k-times enlarged crop whose origin is (left-2, top-2)
---------------------------------------------------------------------------------------------
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))


# =============================================================================== common
def load_rgb(path):
    """Return (rgb int array, PIL RGB image). Transparent pixels are put on white."""
    rgba = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    bg.alpha_composite(rgba)
    rgb = bg.convert("RGB")
    return np.array(rgb).astype(int), rgb


def load_gray(path):
    _, rgb = load_rgb(path)
    return np.array(rgb.convert("L")).astype(int)


def hsv_arrays(rgb_img):
    hsv = np.array(rgb_img.convert("HSV")).astype(float)
    return hsv[..., 0] * 360.0 / 255.0, hsv[..., 1] / 255.0, hsv[..., 2]


def need_openpyxl():
    try:
        import openpyxl  # noqa: F401
        return True
    except ImportError:
        print("openpyxl is not installed -> Excel output skipped (pip install openpyxl)")
        return False


# =============================================================================== presets
COLOR_PRESETS = {'ba_sr': {'name': '(Ba1-xSrx)(Zr0.1Ti0.9)O3, x = 0 .. 0.45, -150..150 C',
           'x_axis': {'auto_ticks': [-150, -100, -50, 0, 50, 100, 150]},
           'y_axis': {'auto_ticks': [0, 6000, 12000, 18000]},
           'ignore': [[10, 92, 165, 262], [57, 119, 96, 180]],
           'room_T': 25,
           'T_range': [-50, 150],
           'sigma_px': 1.5,
           'mark_half_px': 1.5,
           'smooth_window': 1,
           'rel_limit': 0.1,
           'curves': [{'name': 'x=0.05 (blue)', 'color': [0, 0, 255], 'rule': '(B > R + 70) & (B > G + 70)'},
                      {'name': 'x=0.15 (maroon)',
                       'color': [128, 0, 0],
                       'rule': '(R > 85) & (R < 170) & (G < 90) & (B < 90) & (R > G + 40)'},
                      {'name': 'x=0.25 (green)', 'color': [0, 128, 0], 'rule': '(G > R + 35) & (G > B + 35)'},
                      {'name': 'x=0.35 (pink)',
                       'color': [220, 0, 220],
                       'rule': '(R > 200) & (B > 200) & (G > 130) & (G < 215) & (R - G > 25) & (B - G > 25)'},
                      {'name': 'x=0.45 (red)', 'color': [230, 60, 20], 'rule': '(R > 190) & (G < 130) & (B < 120)'}]},
 'x1000': {'name': 'Dielectric constant (x1000) vs T, 30..110 C, x = 0 .. 0.09',
           'x_axis': {'points': [[55.5, 30], [324.0, 110]]},
           'y_axis': {'points': [[36.0, 40000],
                                 [59.5, 35000],
                                 [84.0, 30000],
                                 [108.0, 25000],
                                 [132.0, 20000],
                                 [156.0, 15000],
                                 [180.5, 10000],
                                 [204.5, 5000]]},
           'plot_box': [19, 217, 58, 322],
           'ignore': [[19, 95, 58, 118]],
           'room_T': 30,
           'T_range': [-50, 150],
           'sigma_px': 1.5,
           'mark_half_px': 1.0,
           'smooth_window': 3,
           'rel_limit': 0.1,
           'curves': [{'name': 'x=0 (black)',
                       'color': [0, 0, 0],
                       'rule': '(V < 90) & (S < 0.35)',
                       'rows': [145, 217],
                       'cols': [58, 322],
                       'ignore': [[152, 160, 58, 66], [176, 185, 58, 66], [201, 207, 58, 66]]},
                      {'name': 'x=0.01 (red)',
                       'color': [220, 0, 0],
                       'rule': '((H < 22) | (H > 338)) & (S > 0.30) & (V > 130)',
                       'min_component_px': 60},
                      {'name': 'x=0.03 (blue)',
                       'color': [0, 0, 255],
                       'rule': '(H > 215) & (H < 255) & (S > 0.40) & (V > 70)'},
                      {'name': 'x=0.05 (teal)',
                       'color': [0, 128, 128],
                       'rule': '(H > 150) & (H < 200) & (S > 0.30) & (V > 80)'},
                      {'name': 'x=0.07 (magenta)',
                       'color': [220, 0, 220],
                       'rule': '(H > 275) & (H < 325) & (S > 0.35) & (V > 150)'},
                      {'name': 'x=0.09 (olive)',
                       'color': [128, 128, 0],
                       'rule': '(H > 40) & (H < 85) & (S > 0.35) & (V > 90)'}]}}

BW_PRESET = {'title': '흑백 BaTiO3 유전상수-온도 그래프 디지타이징 결과',
 'excel': 'BaTiO3_흑백그래프_디지타이징.xlsx',
 'description': ['',
                 '원본: fig1_BaTiO3_grainsize.png (Fig.1, 입자 크기별 고순도 BaTiO3 세라믹), fig2_BaTiO3_3transitions.png (Fig.2 '
                 'a,b,c, 1.1um vs 53um, 세 상전이 근처)',
                 '', '방법', ' 1) 축 보정: 프레임 안쪽 짧은 눈금을 픽셀에서 자동으로 찾아, 눈금 값과 1차식으로 맞춤 (맞춤 잔차 x ≤0.18 °C, y ≤10 ε)',
                 ' 2) 곡선 추적: 곡선마다 대략적인 경로(가이드)를 눈으로 지정 → 각 열(급경사 구간은 각 행)에서 가이드에 가장 가까운 검은 선 픽셀의 중심을 읽음',
                 ' 3) 정리: 일정 온도 간격으로 보간해 표로 저장 (Fig1 2 °C, Fig2a 0.5 °C, Fig2b·c 1 °C). 급경사 구간은 ε 약 250 간격',
                 ' 4) 검증: 출력 폴더의 검증_*.png 에 읽은 점을 색깔별로 원본 위에 그려 두었음 → 눈으로 확인 권장', '',
                 '값은 측정점(마커)이 아니라 마커를 잇는 선을 따라 읽은 값입니다. 측정점 자체가 필요하면 마커 위치를 따로 읽어야 합니다.', '',
                 '읽기 오차 (선 두께 ±1~2 px 기준, 대략)', ' Fig1 : 1 px = 0.97 °C, 24.6 ε  → 약 ±2 °C, ±50 ε',
                 ' Fig2a: 1 px = 0.17 °C, 21.0 ε  → 약 ±0.3 °C, ±40 ε',
                 ' Fig2b: 1 px = 0.21 °C, 21.2 ε  → 약 ±0.4 °C, ±40 ε',
                 ' Fig2c: 1 px = 0.21 °C, 21.3 ε  → 약 ±0.4 °C, ±40 ε', '', '주의',
                 ' - cooling = 실선·빈 마커(← 화살표), heating = 점선·채운 마커(→ 화살표)',
                 ' - Fig1: 1.1um, 53um만 전 구간 분리 가능. 1.5/2.2/3.0/13um 곡선은 -140~20 °C와 Tc 근처에서 서로 겹쳐 구분 불가 →',
                 '         구분되는 26~88 °C 구간만 curve A~D로 읽음. A=1.5um(라벨 확인), B·C·D=2.2/3.0/13um는 추정.',
                 ' - Fig1 53um 곡선은 -135~-90 °C에서 다른 곡선(C 또는 D)과 겹쳐 있어 그 구간 값은 두 곡선 공통값일 수 있음',
                 ' - Tc(약 120~125 °C) 위쪽은 모든 곡선이 겹쳐 하나의 공통 곡선으로 읽음',
                 ' - Fig2a 꼭대기(ε > 약 10000) 부근은 곡선 4개가 몇 픽셀 안에 몰려 있어 피크 값 오차가 더 큼'],
 'notes': {'curve A (1.5um)': '라벨로 확인',
           'curve B': '2.2um로 추정 (입자 클수록 eps 작아지는 경향 + 라벨 위치)',
           'curve C': '3.0um로 추정',
           'curve D': '13um로 추정',
           'above Tc (all curves)': '모든 곡선이 겹치는 구간 (구분 불가, 공통값)',
           'above Tc (all curves coincide)': '모든 곡선이 겹치는 구간 (구분 불가, 공통값)'},
 'jobs': [{'sheet': 'Fig1',
           'title': 'Fig.1 grain-size BaTiO3, -150..190 C',
           'file': 'fig1_BaTiO3_grainsize.png',
           'x_ticks': [[146.5, 198.5, 249.5, 301.5, 353.0, 404.5], [-100, -50, 0, 50, 100, 150]],
           'y_ticks': [[52.5, 92.5, 133.5, 174.5, 214.5, 255.5, 296.5, 336.5, 377.5, 418.0, 459.0, 499.5],
                       [12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]],
           'box': [31, 539, 96, 447],
           'k': 4,
           'step': 2.0,
           'y_scale': 1000,
           'curves': {'1.1um': {'ignore': [],
                                'segments': [{'mode': 'x',
                                              'W': 3,
                                              'guide': [[65, 1785], [120, 1755], [175, 1722], [210, 1695],
                                                        [260, 1650], [290, 1622], [320, 1582], [360, 1570],
                                                        [400, 1558], [450, 1535], [490, 1512], [550, 1455],
                                                        [600, 1410], [620, 1380], [660, 1300], [680, 1220],
                                                        [700, 1180], [715, 1168], [740, 1185], [780, 1218],
                                                        [830, 1245], [880, 1255], [940, 1245], [990, 1205],
                                                        [1040, 1130], [1070, 1080]]}]},
                      '53um': {'ignore': [],
                               'segments': [{'mode': 'x',
                                             'W': 3,
                                             'guide': [[65, 1828], [130, 1815], [210, 1798], [260, 1755], [275, 1757],
                                                       [300, 1790], [350, 1840], [400, 1855], [475, 1855],
                                                       [520, 1848], [565, 1832], [610, 1815], [650, 1770],
                                                       [665, 1728], [680, 1735], [720, 1762], [790, 1795],
                                                       [850, 1813], [900, 1818], [1000, 1798], [1080, 1728],
                                                       [1110, 1650], [1124, 1580]]},
                                            {'mode': 'y',
                                             'W': 3,
                                             'guide': [[1126, 1570], [1130, 1400], [1131, 1000]]}]},
                      'curve A (1.5um)': {'ignore': [[330, 355, 282, 350], [338, 362, 212, 262],
                                                     [362, 377, 212, 262]],
                                          'segments': [{'mode': 'x',
                                                        'W': 3,
                                                        'guide': [[730, 1335], [760, 1370], [800, 1410], [830, 1425],
                                                                  [870, 1425], [910, 1415], [970, 1370],
                                                                  [990, 1350]]}]},
                      'curve B': {'ignore': [[330, 355, 282, 350], [338, 362, 212, 262], [362, 377, 212, 262]],
                                  'segments': [{'mode': 'x',
                                                'W': 3,
                                                'guide': [[730, 1380], [760, 1415], [800, 1450], [830, 1462],
                                                          [870, 1465], [920, 1455], [960, 1435], [990, 1410]]}]},
                      'curve C': {'ignore': [[330, 355, 282, 350], [338, 362, 212, 262], [362, 377, 212, 262]],
                                  'segments': [{'mode': 'x',
                                                'W': 3,
                                                'guide': [[730, 1410], [760, 1440], [800, 1475], [830, 1490],
                                                          [870, 1495], [920, 1482], [960, 1455], [990, 1430]]}]},
                      'curve D': {'ignore': [[330, 355, 282, 350], [338, 362, 212, 262], [362, 377, 212, 262]],
                                  'segments': [{'mode': 'x',
                                                'W': 3,
                                                'guide': [[730, 1455], [760, 1490], [800, 1520], [840, 1543],
                                                          [880, 1548], [920, 1540], [970, 1505], [990, 1485]]}]},
                      'above Tc (all curves)': {'ignore': [],
                                                'segments': [{'mode': 'x',
                                                              'W': 3,
                                                              'guide': [[1150, 880], [1165, 1000], [1180, 1150],
                                                                        [1200, 1270], [1225, 1380], [1260, 1530],
                                                                        [1310, 1610], [1350, 1690],
                                                                        [1395, 1780]]}]}}},
          {'sheet': 'Fig2a',
           'title': 'Fig.2(a) cubic-tetragonal, 90..140 C',
           'file': 'fig2_BaTiO3_3transitions.png',
           'x_ticks': [[158.0, 217.5, 277.0, 336.5], [100, 110, 120, 130]],
           'y_ticks': [[82.5, 129.5, 177.5, 225.0, 273.0, 321.0, 368.5, 415.5, 464.0, 511.0],
                       [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]],
           'box': [33, 558, 99, 396],
           'k': 3,
           'step': 0.5,
           'y_scale': 1000,
           'curves': {'1.1um cooling': {'ignore': [[229, 244, 193, 213], [229, 244, 240, 256], [455, 473, 128, 178],
                                                   [444, 452, 223, 244], [465, 473, 255, 279]],
                                        'segments': [{'mode': 'x',
                                                      'W': 5,
                                                      'guide': [[37, 780], [150, 755], [260, 697], [330, 665],
                                                                [400, 600], [445, 490], [487, 420]]},
                                                     {'mode': 'y',
                                                      'W': 3,
                                                      'guide': [[489, 415], [520, 310], [535, 150], [540, 30]]}]},
                      '1.1um heating': {'ignore': [[229, 244, 193, 213], [229, 244, 240, 256], [455, 473, 128, 178],
                                                   [444, 452, 223, 244], [465, 473, 255, 279]],
                                        'segments': [{'mode': 'x',
                                                      'W': 5,
                                                      'guide': [[115, 780], [290, 712], [450, 575], [500, 500]]},
                                                     {'mode': 'y',
                                                      'W': 3,
                                                      'guide': [[502, 495], [510, 480], [540, 385], [550, 305],
                                                                [562, 150], [566, 140]]}]},
                      '53um cooling': {'ignore': [[229, 244, 193, 213], [229, 244, 240, 256], [455, 473, 128, 178],
                                                  [444, 452, 223, 244], [465, 473, 255, 279]],
                                       'segments': [{'mode': 'x',
                                                     'W': 4,
                                                     'guide': [[125, 1348], [235, 1335], [355, 1298], [475, 1245],
                                                               [535, 1192]]},
                                                    {'mode': 'y',
                                                     'W': 3,
                                                     'guide': [[537, 1188], [555, 1150], [568, 1075], [570, 830],
                                                               [572, 500], [575, 150], [580, 40]]}]},
                      '53um heating': {'ignore': [[229, 244, 193, 213], [229, 244, 240, 256], [455, 473, 128, 178],
                                                  [444, 452, 223, 244], [465, 473, 255, 279]],
                                       'segments': [{'mode': 'x',
                                                     'W': 3,
                                                     'guide': [[215, 1355], [340, 1335], [440, 1305], [480, 1292],
                                                               [520, 1270], [555, 1245]]},
                                                    {'mode': 'y',
                                                     'W': 3,
                                                     'guide': [[557, 1240], [575, 1215], [580, 1190], [585, 1100],
                                                               [588, 1025], [592, 700], [592, 390], [585, 165]]}]},
                      'above Tc (all curves coincide)': {'ignore': [[229, 244, 193, 213], [229, 244, 240, 256],
                                                                    [455, 473, 128, 178], [444, 452, 223, 244],
                                                                    [465, 473, 255, 279]],
                                                         'segments': [{'mode': 'x',
                                                                       'W': 4,
                                                                       'guide': [[600, 160], [612, 210], [630, 262],
                                                                                 [655, 370], [685, 470], [715, 600],
                                                                                 [797, 780], [850, 885]]}]}}},
          {'sheet': 'Fig2b',
           'title': 'Fig.2(b) tetragonal-orthorhombic, -20..40 C',
           'file': 'fig2_BaTiO3_3transitions.png',
           'x_ticks': [[569.5, 615.5, 662.5, 709.5, 756.5], [-10, 0, 10, 20, 30]],
           'y_ticks': [[79.5, 125.5, 172.5, 220.5, 267.5], [5, 4, 3, 2, 1]],
           'box': [34, 314, 521, 802],
           'k': 3,
           'step': 1.0,
           'y_scale': 1000,
           'curves': {'1.1um cooling': {'ignore': [[45, 66, 722, 762], [86, 99, 617, 640]],
                                        'segments': [{'mode': 'x',
                                                      'W': 5,
                                                      'guide': [[150, 282], [190, 270], [228, 258], [280, 235],
                                                                [320, 210], [372, 183], [400, 160], [420, 147],
                                                                [462, 118], [495, 100], [530, 85], [570, 86],
                                                                [610, 100], [640, 110], [680, 122], [745, 140]]}]},
                      '1.1um heating': {'ignore': [[45, 66, 722, 762], [85, 97, 683, 708]],
                                        'segments': [{'mode': 'x',
                                                      'W': 5,
                                                      'guide': [[150, 282], [228, 258], [280, 248], [320, 235],
                                                                [372, 212], [406, 198], [455, 178], [510, 155],
                                                                [545, 135], [580, 120], [620, 108], [650, 112],
                                                                [680, 122], [745, 140]]}]},
                      '53um cooling': {'ignore': [[226, 237, 615, 636], [215, 232, 724, 764]],
                                       'segments': [{'mode': 'x',
                                                     'W': 5,
                                                     'guide': [[127, 670], [190, 664], [250, 650], [290, 640],
                                                               [320, 627], [350, 618], [380, 603], [420, 578],
                                                               [432, 568], [460, 573], [490, 578], [510, 585],
                                                               [530, 585], [570, 597], [650, 612], [722, 620]]}]},
                      '53um heating': {'ignore': [[254, 264, 638, 664], [215, 232, 724, 764]],
                                       'segments': [{'mode': 'x',
                                                     'W': 5,
                                                     'guide': [[127, 670], [190, 668], [250, 668], [290, 664],
                                                               [370, 657], [410, 652], [440, 645], [465, 632],
                                                               [485, 612], [500, 592], [520, 580], [530, 583],
                                                               [570, 597], [650, 612], [722, 620]]}]}}},
          {'sheet': 'Fig2c',
           'title': 'Fig.2(c) orthorhombic-rhombohedral, -120..-55 C',
           'file': 'fig2_BaTiO3_3transitions.png',
           'x_ticks': [[570.5, 617.5, 663.5, 710.5, 757.5, 804.5], [-110, -100, -90, -80, -70, -60]],
           'y_ticks': [[416.5, 464.5, 511.0, 557.5], [4, 3, 2, 1]],
           'box': [369, 605, 523, 831],
           'k': 3,
           'step': 1.0,
           'y_scale': 1000,
           'curves': {'1.1um cooling': {'ignore': [[483, 491, 652, 670], [450, 469, 752, 790]],
                                        'segments': [{'mode': 'x',
                                                      'W': 5,
                                                      'guide': [[95, 450], [210, 428], [300, 410], [410, 385],
                                                                [490, 368], [540, 350], [600, 330], [670, 325],
                                                                [740, 318], [800, 305], [875, 305]]}]},
                      '1.1um heating': {'ignore': [[495, 503, 714, 730], [450, 469, 752, 790]],
                                        'segments': [{'mode': 'x',
                                                      'W': 5,
                                                      'guide': [[95, 450], [210, 438], [300, 425], [430, 403],
                                                                [510, 388], [600, 355], [690, 340], [735, 330],
                                                                [790, 312], [875, 305]]}]},
                      '53um cooling': {'ignore': [[524, 532, 600, 622], [549, 566, 752, 790]],
                                       'segments': [{'mode': 'x',
                                                     'W': 5,
                                                     'guide': [[35, 515], [210, 505], [290, 500], [380, 492],
                                                               [430, 483], [470, 465], [495, 458], [520, 468],
                                                               [550, 483], [590, 500], [630, 515], [680, 520],
                                                               [740, 520], [790, 530], [830, 533]]}]},
                      '53um heating': {'ignore': [[545, 553, 664, 687], [549, 566, 752, 790]],
                                       'segments': [{'mode': 'x',
                                                     'W': 5,
                                                     'guide': [[35, 515], [120, 518], [300, 517], [500, 517],
                                                               [600, 515], [640, 512], [670, 500], [697, 487],
                                                               [715, 500], [740, 518], [790, 530], [830, 533]]}]}}}]}


# =============================================================================== COLOR mode
def find_axes(im):
    """Auto mode: pixel positions of x ticks (cols) and y ticks (rows) + axis lines."""
    gray = im.sum(axis=2) / 3
    dark = gray < 160
    rows = dark.sum(axis=1)
    cols = dark.sum(axis=0)
    bottom = [r for r in range(im.shape[0]) if rows[r] > 200][-2:]
    cl = [c for c in range(im.shape[1]) if cols[c] > 150]
    left, right = cl[0], cl[-1]
    y_axis_row = sum(bottom) / len(bottom)
    below = dark[int(max(bottom)) + 1:int(max(bottom)) + 6, :]
    xt = [c for c in range(left - 2, right + 3) if below[:, c].sum() >= 3]
    groups = []
    for c in xt:
        if not groups or c - groups[-1][-1] > 1:
            groups.append([c])
        else:
            groups[-1].append(c)
    x_cols = [float(np.mean(g)) for g in groups]
    leftof = dark[:, left - 7:left]
    yt = [r for r in range(im.shape[0]) if leftof[r, :].sum() >= 4 and r < min(bottom) - 5]
    return x_cols, yt, y_axis_row, left, right


def axis_fit(spec, auto_pixels, kind):
    """Return (a, b) with value = a*pixel + b."""
    if "points" in spec:
        px = [p[0] for p in spec["points"]]
        val = [p[1] for p in spec["points"]]
    else:
        vals = list(spec["auto_ticks"])
        if kind == "y":                    # rows grow downward, values upward
            px = sorted(auto_pixels)
            val = sorted(vals, reverse=True)
        else:
            px = auto_pixels
            val = vals
        if len(px) != len(val):
            raise SystemExit(f"{kind}-axis: found {len(px)} ticks {px}, expected {len(val)}")
    a, b = np.polyfit(px, val, 1)
    return a, b


def class_mask(cfg_curve, ns, plot_mask):
    m = eval(cfg_curve["rule"], {"np": np}, ns) & plot_mask
    if "rows" in cfg_curve:
        r0, r1 = cfg_curve["rows"]
        keep = np.zeros_like(m)
        keep[r0:r1, :] = True
        m &= keep
    if "cols" in cfg_curve:
        c0, c1 = cfg_curve["cols"]
        keep = np.zeros_like(m)
        keep[:, c0:c1] = True
        m &= keep
    for a0, a1, b0, b1 in cfg_curve.get("ignore", []):     # per-curve exclusion (e.g. axis tick marks)
        m[a0:a1, b0:b1] = False
    n_min = cfg_curve.get("min_component_px", 0)
    if n_min:
        from scipy import ndimage as ndi
        lab, n = ndi.label(m, structure=np.ones((3, 3)))
        sizes = ndi.sum(m, lab, range(1, n + 1))
        for i, s in enumerate(sizes, start=1):
            if s < n_min:
                m[lab == i] = False
    return m


def envelope(mask, col0, col1):
    """Per column: (top_row, median_row, bottom_row) of the class pixels."""
    env = {}
    for c in range(col0, col1 + 1):
        rr = np.nonzero(mask[:, c])[0]
        if len(rr):
            env[c] = (float(rr.min()), float(np.median(rr)), float(rr.max()))
    return env


def smoothed_tops(env, w):
    cols = sorted(env)
    tops = {c: env[c][0] for c in cols}
    if w <= 1:
        return tops
    half = w // 2
    out = {}
    for c in cols:
        vals = [env[k][0] for k in range(c - half, c + half + 1) if k in env]
        out[c] = float(np.median(vals))
    return out


def run_color(args):
    if args.config:
        cfg_path = args.config
        cfg = json.load(open(cfg_path, encoding="utf-8"))
    else:
        cfg_path = f"(built-in preset: {args.preset})"
        cfg = COLOR_PRESETS[args.preset]
    stem = os.path.splitext(os.path.basename(args.image))[0]
    outdir = args.outdir or os.path.dirname(os.path.abspath(args.image))
    os.makedirs(outdir, exist_ok=True)

    im, rgb_img = load_rgb(args.image)
    H_, W_, _ = im.shape
    R, G, B = im[..., 0], im[..., 1], im[..., 2]
    Hh, Ss, Vv = hsv_arrays(rgb_img)
    ns = {"R": R, "G": G, "B": B, "H": Hh, "S": Ss, "V": Vv}

    # ---- calibration
    auto = "auto_ticks" in cfg["x_axis"] or "auto_ticks" in cfg["y_axis"]
    if auto:
        x_cols, yt, y_axis_row, left, right = find_axes(im)
        y_pix = list(yt) + [y_axis_row]
    else:
        x_cols, y_pix = None, None
    ax, bx = axis_fit(cfg["x_axis"], x_cols, "x")
    ay, by = axis_fit(cfg["y_axis"], y_pix, "y")
    T = lambda c: ax * c + bx
    E = lambda r: ay * r + by
    col_of = lambda t: (t - bx) / ax
    deg_per_px, eps_per_px = abs(ax), abs(ay)

    if "plot_box" in cfg:
        r0, r1, c0, c1 = cfg["plot_box"]
    else:
        r0, r1, c0, c1 = 14, int(y_axis_row) - 2, left + 3, right - 1
    plot = np.zeros((H_, W_), bool)
    plot[r0:r1, c0:c1] = True
    for a0, a1, b0, b1 in cfg.get("ignore", []):
        plot[a0:a1, b0:b1] = False

    sigma = cfg.get("sigma_px", 1.5)
    half = cfg.get("mark_half_px", 1.5)
    rel_limit = cfg.get("rel_limit", 0.10)
    room_T = cfg.get("room_T", 25.0)
    Tlo_req, Thi_req = cfg.get("T_range", [-50.0, 150.0])
    win = cfg.get("smooth_window", 1)
    T_vis = sorted([T(c0), T(c1)])
    Tlo, Thi = max(Tlo_req, T_vis[0]), min(Thi_req, T_vis[1])

    lines = []
    out = lines.append
    out(f"image  : {args.image}")
    out(f"config : {cfg_path}")
    out(f"calibration: {deg_per_px:.3f} C/px, {eps_per_px:.1f} eps/px; sigma = {sigma} px "
        f"-> +-{sigma * deg_per_px:.2f} C, +-{sigma * eps_per_px:.0f} eps")
    out(f"visible T range in the figure: {T_vis[0]:.1f} .. {T_vis[1]:.1f} C")
    if (Tlo, Thi) != (Tlo_req, Thi_req):
        out(f"NOTE: requested min/max window {Tlo_req}..{Thi_req} C is wider than the figure; "
            f"using {Tlo:.1f}..{Thi:.1f} C")
    edge_tol = 3 * deg_per_px          # the search box stops ~3 px inside the frame; allow reading right at the edge
    room_ok = T_vis[0] - edge_tol <= room_T <= T_vis[1] + edge_tol
    if room_ok and not (T_vis[0] <= room_T <= T_vis[1]):
        out(f"NOTE: {room_T:g} C lies at the very edge of the figure; read from the nearest curve pixels "
            f"(offset added to the error)")
    if not room_ok:
        out(f"NOTE: room temperature {room_T} C is outside the plotted range -> cannot be read")

    def fmt(val, err):
        rel = err / abs(val) if val else float("inf")
        tag = "OK" if rel <= rel_limit else "읽기불가"
        return f"{val:8.0f} +-{err:5.0f} ({rel * 100:4.1f}%) {tag}"

    def cell(val, err):                # same value as fmt(), as Excel columns (value, error, rel %, status)
        rel = err / abs(val) if val else float("inf")
        return [round(float(val)), round(float(err)), round(rel * 100, 1), "OK" if rel <= rel_limit else "읽기불가"]

    out("")
    out(f"{'curve':16s} | {'peak eps':32s} | {'peak T (C)':16s} | {'eps @%gC' % room_T:32s} | "
        f"{'min eps (%.0f..%.0fC)' % (Tlo, Thi):32s}")

    overlay = rgb_img.resize((W_ * 3, H_ * 3), Image.NEAREST)
    d = ImageDraw.Draw(overlay)
    d.rectangle([c0 * 3, r0 * 3, c1 * 3, r1 * 3], outline=(170, 170, 170))
    for a0, a1, b0, b1 in cfg.get("ignore", []):
        d.rectangle([b0 * 3, a0 * 3, b1 * 3, a1 * 3], outline=(200, 160, 160))

    results = []
    refs = []
    table = []                         # rows for the Excel sheet
    for cv in cfg["curves"]:
        name = cv["name"]
        m = class_mask(cv, ns, plot)
        if not m.any():
            out(f"{name:16s} | no pixels found")
            table.append([name, "no pixels found"])
            continue
        env = envelope(m, c0, c1 - 1)
        cols = sorted(env)
        tops = smoothed_tops(env, win)
        # ---- peak: highest (smoothed) top pixel, + half width -> centre
        top_row = min(tops.values())
        pk_cols = [c for c in cols if tops[c] <= top_row + 1]
        pk_col = float(np.mean(pk_cols))
        pk_eps = E(top_row + half)
        pk_T = T(pk_col)
        pk_err = sigma * eps_per_px
        pk_T_err = max(sigma, (max(pk_cols) - min(pk_cols)) / 2) * deg_per_px
        row = [name] + cell(pk_eps, pk_err) + [round(pk_T, 1), round(pk_T_err, 1)]
        # ---- eps at room temperature
        if room_ok:
            c25 = col_of(room_T)
            c_use = min(max(c25, c0 + 2), c1 - 3)          # clamp to the searchable area
            offset_px = abs(c_use - c25)
            near = [c for c in cols if abs(c - c_use) <= 1.5]
            if near:
                r25 = float(np.mean([env[c][1] for c in near]))
                loc = [c for c in cols if abs(c - c_use) <= 4]
                slope_px = 0.0                                 # |d eps| per column
                if len(loc) >= 3:
                    k = np.polyfit(loc, [env[c][1] for c in loc], 1)[0]
                    slope_px = abs(k) * eps_per_px
                e25 = E(r25)
                e25_err = float(np.hypot(sigma * eps_per_px, slope_px * (sigma + offset_px)))
                s25 = fmt(e25, e25_err)
                row += cell(e25, e25_err)
            else:
                s25 = "n/a"
                row += ["", "", "", "n/a"]
        else:
            s25 = "범위 밖"
            row += ["", "", "", "범위 밖"]
        # ---- min eps in the T window
        cwin = sorted([col_of(Tlo), col_of(Thi)])
        cr = [c for c in cols if cwin[0] <= c <= cwin[1]]
        if cr:
            bot_row = max(env[c][2] for c in cr)
            mn = E(bot_row - half)
            gaps = [b - a for a, b in zip(cr, cr[1:])]
            if min(cr) > cwin[0] + 4 or max(cr) < cwin[1] - 4 or (gaps and max(gaps) > 6):
                # curve not found over the whole window -> its true minimum may lie outside what was detected
                smin = f"n/a (곡선이 구간 전체에서 검출 안 됨: T={T(min(cr)):.0f}~{T(max(cr)):.0f}C) 읽기불가"
                row += ["", "", "", smin]
            elif bot_row >= r1 - 2:    # curve runs into the lower axis/search-box edge
                smin = f"<={mn:7.0f} (축 하단에 닿음) 읽기불가"
                row += [f"<={mn:.0f}", "", "", "축 하단에 닿음, 읽기불가"]
            else:
                smin = fmt(mn, sigma * eps_per_px)
                row += cell(mn, sigma * eps_per_px)
        else:
            mn, smin = None, "n/a"
            row += ["", "", "", "n/a"]
        # reference value at the visible edge nearest to room temperature (only when room T is out of range)
        if not room_ok:
            t_ref_col = c0 + 3 if abs(T(c0) - room_T) < abs(T(c1) - room_T) else c1 - 4
            nr = [c for c in cols if abs(c - t_ref_col) <= 1.5]
            if nr:
                rr_ = float(np.mean([env[c][1] for c in nr]))
                refs.append((name, T(t_ref_col), E(rr_)))
        out(f"{name:16s} | {fmt(pk_eps, pk_err):32s} | {pk_T:6.1f} +-{pk_T_err:4.1f}    | {s25:32s} | {smin:32s}")
        results.append((name, pk_eps, pk_T))
        table.append(row)

        # overlay: curve centre line, peak cross + label
        col = tuple(cv.get("color", [0, 0, 0]))
        for c in cols:
            d.point((c * 3 + 1, env[c][1] * 3 + 1), fill=col)
        x, y = pk_col * 3 + 1, (top_row + half) * 3 + 1
        d.line([(x - 7, y), (x + 7, y)], fill=(0, 190, 0), width=1)
        d.line([(x, y - 7), (x, y + 7)], fill=(0, 190, 0), width=1)
        d.text((x + 9, y - 6), f"{pk_eps:.0f} @ {pk_T:.1f}C", fill=col)

    if room_ok:
        x25 = col_of(room_T) * 3 + 1
        d.line([(x25, r0 * 3), (x25, r1 * 3)], fill=(150, 150, 150), width=1)

    # ---- overall (all curves together) max / min inside the window
    if results:
        n_best = max(results, key=lambda t: t[1])
        out("")
        out(f"전체 최대(모든 곡선 중): {fmt(n_best[1], sigma * eps_per_px)} at T={n_best[2]:.1f} C  [{n_best[0]}]")
        anyline = ((Ss > 0.25) | (Vv < 140)) & plot
        cw = sorted([int(col_of(Tlo)), int(col_of(Thi))])
        edge_cols = list(range(cw[1] - 6, cw[1] + 1))      # right end: all curves converge here
        rows_ = [r for c in edge_cols for r in np.nonzero(anyline[:, c])[0]]
        if rows_:
            bot = max(rows_)
            mn_all = E(bot - half)
            if bot >= r1 - 2:
                out(f"전체 최소(모든 곡선 중): <={mn_all:.0f} (축 하단에 닿음) 읽기불가")
            else:
                out(f"전체 최소(모든 곡선 중): {fmt(mn_all, sigma * eps_per_px)} at T~{T(edge_cols[-1]):.0f} C "
                    f"(곡선들이 겹쳐 어느 조성인지는 구분 불가)")
    if refs:
        out(f"참고: 상온({room_T:g} C)이 범위 밖이라, 그래프 가장자리(T={refs[0][1]:.1f} C)에서 읽은 값 "
            f"(상온 값이 아님, 가장자리는 곡선이 흔들려 오차가 더 클 수 있음)")
        for n_, t_, e_ in refs:
            out(f"   {n_:16s} eps({t_:.1f} C) = {e_:8.0f} +-{sigma * eps_per_px:5.0f}")
    res_path = os.path.join(outdir, f"{stem}_results.txt")
    ov_path = os.path.join(outdir, f"{stem}_overlay.png")
    xl_path = os.path.join(outdir, f"{stem}_results.xlsx")
    out("")
    out(f"overlay: {ov_path}  (green cross + label = detected peak; gray box = search area; "
        f"pink boxes = ignored areas; dots = detected curve centre)")
    text = "\n".join(lines)
    print(text)
    with open(res_path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    overlay.save(ov_path)

    if need_openpyxl():
        from openpyxl import Workbook
        from openpyxl.styles import Font
        wb = Workbook()
        ws = wb.active
        ws.title = "결과"
        ws.append(["곡선", "최대 ε", "±", "상대오차 %", "판정", "최대 T (°C)", "± (°C)",
                   f"ε @{room_T:g}°C", "±", "상대오차 %", "판정",
                   f"최소 ε ({Tlo:.0f}~{Thi:.0f}°C)", "±", "상대오차 %", "판정"])
        for c_ in ws[1]:
            c_.font = Font(bold=True)
        for row in table:
            ws.append(row)
        ws.column_dimensions["A"].width = 20
        ws2 = wb.create_sheet("원문 출력")
        for line in lines:
            ws2.append([line])
        wb.save(xl_path)
        print(f"excel  : {xl_path}")


# =============================================================================== BW mode
def _fit(ticks):
    px, val = ticks
    a, b = np.polyfit(px, val, 1)
    resid = float(np.std(np.array(val) - (a * np.array(px) + b)))
    return a, b, resid


def _runs(v, merge=2):
    idx = np.nonzero(v)[0]
    if not len(idx):
        return []
    sp = np.split(idx, np.nonzero(np.diff(idx) > merge + 1)[0] + 1)
    return [(s[0], s[-1]) for s in sp]


def trace_curve(gray, job, curve, thr=150):
    """Guide-assisted tracing. Returns [(T, eps, col, row, mode), ...]."""
    ax, bx, _ = _fit(job["x_ticks"])
    ay, by, _ = _fit(job["y_ticks"])
    ys = job.get("y_scale", 1000)
    t, b, l, r = job["box"]
    k = job["k"]
    d = gray < thr
    for (r0, r1, c0, c1) in curve.get("ignore", []):
        d[r0:r1, c0:c1] = False
    pts = []
    for seg in curve["segments"]:
        G = np.array(seg["guide"], float)
        gc = (l - 2) + G[:, 0] / k
        gr = (t - 2) + G[:, 1] / k                            # guide in original px
        W = seg.get("W", 4)
        if seg["mode"] == "x":
            o = np.argsort(gc)
            gc, gr = gc[o], gr[o]
            for col in range(int(np.ceil(gc[0])), int(np.floor(gc[-1])) + 1):
                g = np.interp(col, gc, gr)
                lo, hi = int(g - W), int(g + W) + 1
                rr = [(a + lo, z + lo) for a, z in _runs(d[lo:hi, col])]
                rr = [x for x in rr if x[1] - x[0] <= 9]
                if rr:
                    a, z = min(rr, key=lambda x: abs((x[0] + x[1]) / 2 - g))
                    pts.append((col, (a + z) / 2, "x"))
        else:
            o = np.argsort(gr)
            gc, gr = gc[o], gr[o]
            for row in range(int(np.ceil(gr[0])), int(np.floor(gr[-1])) + 1):
                g = np.interp(row, gr, gc)
                lo, hi = int(g - W), int(g + W) + 1
                cc = [(a + lo, z + lo) for a, z in _runs(d[row, lo:hi])]
                cc = [x for x in cc if x[1] - x[0] <= 9]
                if cc:
                    a, z = min(cc, key=lambda x: abs((x[0] + x[1]) / 2 - g))
                    pts.append(((a + z) / 2, row, "y"))
    return [(ax * x + bx, (ay * y + by) * ys, x, y, m) for x, y, m in pts]


def resample(out, step):
    """x-mode points -> values at round T; y-mode points (steep parts) -> every ~250 of eps."""
    xs = sorted([o for o in out if o[4] == "x"], key=lambda o: o[0])
    ys = sorted([o for o in out if o[4] == "y"], key=lambda o: o[1])
    rows = []
    if xs:
        T = np.array([o[0] for o in xs])
        E = np.array([o[1] for o in xs])
        for t in np.arange(np.ceil(T[0] / step) * step, T[-1] + 1e-9, step):
            j = np.searchsorted(T, t)
            near = min(abs(T[max(j - 1, 0)] - t), abs(T[min(j, len(T) - 1)] - t))
            if near <= max(step / 2, 0.6):
                rows.append((round(float(t), 2), round(float(np.interp(t, T, E))), "열 단위 추적"))
    if ys:
        last = -1e9
        for o in ys:
            if o[1] - last >= 250:
                rows.append((round(float(o[0]), 2), round(float(o[1])), "급경사: 행 단위 추적"))
                last = o[1]
    return rows


OVERLAY_COLORS = [(255, 0, 0), (0, 170, 0), (0, 140, 255), (220, 0, 220), (255, 140, 0), (0, 190, 190), (120, 60, 255)]


def run_bw(args):
    if args.config:
        preset = json.load(open(args.config, encoding="utf-8"))
        src = args.config
    else:
        preset = BW_PRESET
        src = "built-in BaTiO3 grain-size preset"
    images = args.images or (os.path.dirname(os.path.abspath(args.config)) if args.config
                             else os.path.join(HERE, "bw_test"))
    outdir = args.outdir or images
    os.makedirs(outdir, exist_ok=True)
    notes = preset.get("notes", {})
    print(f"config : {src}")
    print(f"images : {images}")

    have_xl = need_openpyxl()
    if have_xl:
        from openpyxl import Workbook
        from openpyxl.chart import ScatterChart, Reference, Series
        from openpyxl.styles import Font
        wb = Workbook()
        info = wb.active
        info.title = "설명"

    summary = []
    for job in preset["jobs"]:
        path = os.path.join(images, job["file"])
        gray = load_gray(path)
        ax, bx, rx = _fit(job["x_ticks"])
        ay, by, ry = _fit(job["y_ticks"])
        ysc = job.get("y_scale", 1000)
        print(f"{job['sheet']}: {abs(ax):.4f} C/px, {abs(ay) * ysc:.1f} eps/px  "
              f"(fit residual x {rx:.3f} C, y {ry * ysc:.1f} eps)")
        t, b, l, r = job["box"]
        im = Image.open(path).convert("RGB").crop((l - 2, t - 2, r + 3, b + 3))
        im = im.resize((im.width * 4, im.height * 4), Image.NEAREST)
        dr = ImageDraw.Draw(im)
        if have_xl:
            ws = wb.create_sheet(job["sheet"])
            ws.append([job["title"]])
            ws["A1"].font = Font(bold=True)
            ws.append(["곡선", "T (°C)", "유전상수 ε", "읽은 방식", "비고"])
            for c_ in ws[2]:
                c_.font = Font(bold=True)
            chart = ScatterChart()
            chart.title = job["title"]
            chart.style = 13
            chart.x_axis.title = "Temperature (°C)"
            chart.y_axis.title = "Dielectric constant"
            chart.height, chart.width = 12, 20
        for i, (cn, cv) in enumerate(job["curves"].items()):
            out = trace_curve(gray, job, cv)
            if not out:
                print(f"   {cn}: no line pixels found near the guide")
                continue
            data = resample(out, job["step"])
            if have_xl:
                r0 = ws.max_row + 1
                for T_, E_, how in data:
                    ws.append([cn, T_, E_, how, notes.get(cn, "")])
                r1 = ws.max_row
                s = Series(Reference(ws, min_col=3, min_row=r0, max_row=r1),
                           Reference(ws, min_col=2, min_row=r0, max_row=r1), title=cn)
                s.marker.symbol = "circle"
                s.marker.size = 3
                s.smooth = False
                chart.series.append(s)
            pk = max(data, key=lambda x: x[1])
            summary.append([job["sheet"], cn, len(data), min(x[0] for x in data), max(x[0] for x in data), pk[1], pk[0]])
            colr = OVERLAY_COLORS[i % len(OVERLAY_COLORS)]
            for T_, E_, x, y, m in out:
                X = (x - (l - 2)) * 4 + 2
                Y = (y - (t - 2)) * 4 + 2
                dr.rectangle([X - 1, Y - 1, X + 1, Y + 1], fill=colr)
            X, Y = 8, 8 + 18 * i
            dr.rectangle([X, Y, X + 12, Y + 12], fill=colr)
            dr.text((X + 18, Y), cn, fill=colr)
        if have_xl:
            for col, w in zip("ABCDE", (30, 10, 12, 20, 50)):
                ws.column_dimensions[col].width = w
            ws.add_chart(chart, "G3")
        ov = os.path.join(outdir, f"검증_{job['sheet']}.png")
        im.save(ov)

    print("")
    print(f"{'sheet':6s} | {'curve':32s} | points | T range (C)      | max eps @ T")
    for s in summary:
        print(f"{s[0]:6s} | {s[1]:32s} | {s[2]:6d} | {s[3]:7.1f} .. {s[4]:6.1f} | {s[5]:6d} @ {s[6]:.1f}")
    print(f"check images: {outdir}{os.sep}검증_*.png")

    if have_xl:
        info.append([preset.get("title", "흑백 그래프 디지타이징 결과")])
        info["A1"].font = Font(bold=True, size=13)
        for line in preset.get("description", []):
            info.append([line])
        info.append([])
        info.append(["요약: 시트", "곡선", "점 개수", "T 최소", "T 최대", "최대 ε", "최대 ε 온도"])
        for c_ in info[info.max_row]:
            c_.font = Font(bold=True)
        for s in summary:
            info.append(s)
        info.column_dimensions["A"].width = 14
        info.column_dimensions["B"].width = 32
        xl = os.path.join(outdir, preset.get("excel", "bw_digitized.xlsx"))
        wb.save(xl)
        print(f"excel : {xl}")


# =============================================================================== TICKS mode
def _line_segments(mask, min_len):
    """Long dark runs along rows of `mask`, merged over adjacent rows -> [pos_lo, pos_hi, start, end]."""
    segs = []
    for i, row in enumerate(mask):
        for a, z in _runs(row, merge=2):
            if z - a + 1 >= min_len:
                segs.append([i, i, int(a), int(z)])
    merged = []
    for s in segs:
        for m in merged:
            overlap = min(s[3], m[3]) - max(s[2], m[2])
            if 0 <= s[0] - m[1] <= 1 and overlap > 0.8 * min(s[3] - s[2], m[3] - m[2]):
                m[1] = s[0]
                m[2], m[3] = min(m[2], s[2]), max(m[3], s[3])
                break
        else:
            merged.append(list(s))
    return merged


def _band(m, line, horizontal, min_cov=0.3):
    """Rows (or columns) near a detected line that really belong to it -> [lo, hi]."""
    lo, hi, a, z = line
    M = m if horizontal else m.T
    rows = [q for q in range(max(lo - 2, 0), min(hi + 3, M.shape[0])) if M[q, a:z + 1].mean() >= min_cov]
    return [min(rows), max(rows), a, z] if rows else list(line)


def find_frames(d, min_frac=0.15, min_size=30):
    """Rectangular plot frames: pairs of long horizontal + vertical lines that close a box.
    `d` = dark mask (use a loose threshold: scanned frame lines are often gray and wander over 2 rows).
    Returns [(top_line, bottom_line, left_line, right_line)], each line = [pos_lo, pos_hi, start, end]."""
    H, W = d.shape
    dh = d.copy()
    dh[1:] |= d[:-1]                       # a line drifting between two rows still forms one long run
    dv = d.copy()
    dv[:, 1:] |= d[:, :-1]
    hl = [_band(d, s, True) for s in _line_segments(dh, max(40, int(min_frac * W)))]
    vl = [_band(d, s, False) for s in _line_segments(dv.T, max(40, int(min_frac * H)))]
    rects = []
    for t in hl:
        for b in hl:
            if b[0] - t[1] < min_size:
                continue
            for l in vl:
                for r in vl:
                    if r[0] - l[1] < min_size:
                        continue
                    if (t[2] <= l[1] + 3 and t[3] >= r[0] - 3 and b[2] <= l[1] + 3 and b[3] >= r[0] - 3 and
                            l[2] <= t[1] + 3 and l[3] >= b[0] - 3 and r[2] <= t[1] + 3 and r[3] >= b[0] - 3):
                        rects.append((t, b, l, r))

    def inside(a, b):          # a strictly inside b (or equal box drawn by other lines)
        return (a is not b and a[0][0] >= b[0][0] and a[1][1] <= b[1][1] and
                a[2][0] >= b[2][0] and a[3][1] <= b[3][1])
    rects = [r for r in rects if not any(inside(o, r) for o in rects)]
    return sorted(rects, key=lambda r: (r[0][0] // 40, r[2][0]))


def _edge_ticks(d, line, horizontal, span, direction, max_len=12):
    """Tick candidates sticking out of one frame line. direction -1 / +1 = towards smaller / larger index."""
    lo, hi = line[0], line[1]
    start = lo - 1 if direction < 0 else hi + 1
    lens = {}
    for p in range(span[0] + 3, span[1] - 2):
        n = 0
        q = start
        while 0 <= q < (d.shape[0] if horizontal else d.shape[1]) and n <= max_len + 1:
            if not (d[q, p] if horizontal else d[p, q]):
                break
            n += 1
            q += direction
        if 2 <= n <= max_len:
            lens[p] = n
    cands = []
    for g in _runs(np.array([p in lens for p in range(d.shape[1] if horizontal else d.shape[0])]), merge=0):
        if g[1] - g[0] <= 3:                      # thin -> tick, wide -> a curve touching the frame
            ps = list(range(g[0], g[1] + 1))
            cands.append((round(float(np.mean(ps)), 1), max(lens[p] for p in ps)))
    return cands


def _spacing_fit(cands, tol=1.5, min_spacing=6):
    """Largest subset of candidates lying on an evenly spaced grid. Returns (inliers, spacing).
    The tolerance shrinks with the spacing (max 12 % of it) so a tiny spacing cannot 'fit' everything."""
    pos = [c[0] for c in cands]
    best = (0, 0.0, [])
    for i in range(len(pos)):
        for j in range(i + 1, len(pos)):
            for m in range(1, j - i + 1):
                s = (pos[j] - pos[i]) / m
                if s < min_spacing:
                    continue
                t_ = min(tol, 0.12 * s)
                slot = {}                                   # one tick per grid slot: the closest one
                for c in cands:
                    q = (c[0] - pos[i]) / s
                    k, off = round(q), abs(q - round(q)) * s
                    if off <= t_ and (k not in slot or off < slot[k][0]):
                        slot[k] = (off, c)
                if len(slot) < 3:
                    continue
                inl = [slot[k][1] for k in sorted(slot)]
                empty = (max(slot) - min(slot) + 1) - len(slot)
                score = len(slot) - 0.5 * empty             # half spacing would leave every other slot empty
                if (score, s) > (best[0], best[1]):
                    best = (score, s, inl)
    if best[0] < 3:
        return list(cands), None
    inl = best[2]
    for _ in range(2):                                  # refine: fit the grid, then re-pick the closest tick per slot
        k = np.round((np.array([c[0] for c in inl]) - inl[0][0]) / best[1])
        s, p0 = np.polyfit(k, [c[0] for c in inl], 1)
        t_ = min(tol, 0.12 * s)
        slot = {}
        for c in cands:
            q = (c[0] - p0) / s
            kk, off = round(q), abs(c[0] - (p0 + round(q) * s))
            if off <= t_ and (kk not in slot or off < slot[kk][0]):
                slot[kk] = (off, c)
        inl = [slot[kk][1] for kk in sorted(slot)]
    return inl, float(s)


def run_ticks(args):
    path = args.image
    stem = os.path.splitext(os.path.basename(path))[0]
    outdir = args.outdir or os.path.dirname(os.path.abspath(path))
    os.makedirs(outdir, exist_ok=True)
    gray = load_gray(path)
    d = gray < args.thr                    # ticks
    H_, W_ = d.shape

    if args.box:
        frames = []
        dl = gray < 200
        for spec in args.box:
            t, b, l, r = [int(v) for v in spec.split(",")]
            frames.append((_band(dl, [t, t, l, r], True), _band(dl, [b, b, l, r], True),
                           _band(dl, [l, l, t, b], False), _band(dl, [r, r, t, b], False)))
    else:
        frames = find_frames(gray < 200)
    if not frames:
        raise SystemExit("no rectangular plot frame found -> give it by hand: --box top,bottom,left,right")

    ov = Image.open(path).convert("RGB").resize((W_ * 3, H_ * 3), Image.NEAREST)
    dr = ImageDraw.Draw(ov)
    jobs = []
    lines = [f"image : {path}", f"found {len(frames)} plot frame(s)  (pixel = original image px; tick 'len' = length in px, "
             f"long ticks are usually the labelled ones)", ""]
    for n, (tl, bl, ll, rl) in enumerate(frames):
        letter = chr(ord("a") + n)
        top, bot = int(round((tl[0] + tl[1]) / 2)), int(round((bl[0] + bl[1]) / 2))
        left, right = int(round((ll[0] + ll[1]) / 2)), int(round((rl[0] + rl[1]) / 2))
        edges = {
            "bottom": (bl, True, (left, right)), "top": (tl, True, (left, right)),
            "left": (ll, False, (top, bot)), "right": (rl, False, (top, bot)),
        }
        found = {}
        for name, (line, horiz, span) in edges.items():
            best = None
            for direction in (-1, 1):
                cands = _edge_ticks(d, line, horiz, span, direction)
                inl, s = _spacing_fit(cands)
                inward = (name in ("bottom", "right")) == (direction < 0)
                key = (s is not None, len(inl))
                if best is None or key > best[0]:
                    best = (key, inl, s, cands, "inward" if inward else "outward")
            found[name] = best
        lines.append(f"[panel {letter}]  box (top, bottom, left, right) = [{top}, {bot}, {left}, {right}]")
        for name in ("bottom", "left", "top", "right"):
            (_, inl, s, cands, side) = found[name]
            if not cands:
                lines.append(f"   {name:6s}: no ticks")
                continue
            sp = f"spacing {s:.2f} px" if s else "no even spacing found (check by eye)"
            lines.append(f"   {name:6s}: {len(inl)} ticks ({side}), {sp}")
            lines.append("            #   " + "  ".join(f"{i:>6d}" for i in range(len(inl))))
            lines.append("            px  " + "  ".join(f"{c[0]:6.1f}" for c in inl))
            lines.append("            len " + "  ".join(f"{c[1]:6d}" for c in inl))
            rej = [c for c in cands if c not in inl]
            if rej:
                lines.append("            not on the even grid (curve/label?): " + ", ".join(f"{c[0]:.1f}" for c in rej))
        lines.append("")

        # overlay: frame (blue), ticks (red, numbered), rejected candidates (orange)
        dr.rectangle([left * 3, top * 3, right * 3 + 2, bot * 3 + 2], outline=(0, 90, 255), width=2)
        dr.text((left * 3 + 6, top * 3 + 4), f"panel {letter}", fill=(0, 90, 255))
        for name in ("bottom", "left", "top", "right"):
            (_, inl, s, cands, side) = found[name]
            for c in cands:
                p = c[0] * 3 + 1
                colr = (230, 0, 0) if c in inl else (255, 150, 0)
                if name in ("bottom", "top"):
                    y = (bot if name == "bottom" else top) * 3 + 1
                    dr.line([(p, y - 12), (p, y + 12)], fill=colr, width=2)
                    if c in inl and name == "bottom":
                        dr.text((p - 3, y + 14), str(inl.index(c)), fill=colr)
                else:
                    x = (left if name == "left" else right) * 3 + 1
                    dr.line([(x - 12, p), (x + 12, p)], fill=colr, width=2)
                    if c in inl and name == "left":
                        dr.text((x + 14, p - 6), str(inl.index(c)), fill=colr)

        xs = found["bottom"] if len(found["bottom"][1]) >= 2 else found["top"]
        ys = found["left"] if len(found["left"][1]) >= 2 else found["right"]
        jobs.append({
            "sheet": f"panel_{letter}", "title": f"{stem} panel {letter}", "file": os.path.basename(path),
            "x_ticks": [[c[0] for c in xs[1]], [None] * len(xs[1])],
            "y_ticks": [[c[0] for c in ys[1]], [None] * len(ys[1])],
            "box": [top, bot, left, right], "k": 4, "step": 1.0, "y_scale": 1000, "curves": {},
            "_memo": "x_ticks[1] / y_ticks[1]: write the axis value of each tick (same order as the pixels; "
                     "y pixels run top -> bottom). y_scale 1000 = y values written in units of 10^3. "
                     "Remove ticks you cannot label from BOTH lists. Then add curves (see the file header).",
            "_tick_lengths": {"x": [c[1] for c in xs[1]], "y": [c[1] for c in ys[1]]},
        })

    js = os.path.join(outdir, f"{stem}_ticks.json")
    png = os.path.join(outdir, f"{stem}_ticks.png")
    txt = os.path.join(outdir, f"{stem}_ticks.txt")
    with open(js, "w", encoding="utf-8") as f:
        json.dump({"title": stem, "excel": f"{stem}_trace.xlsx", "description": [], "notes": {}, "jobs": jobs},
                  f, ensure_ascii=False, indent=1)
    ov.save(png)
    lines += [f"check image : {png}  (blue = frame, red = ticks on the even grid with their # number, "
              f"orange = rejected)",
              f"config draft: {js}  (fill in the tick values -> add curves -> run: bw --config ...)"]
    text = "\n".join(lines)
    print(text)
    with open(txt, "w", encoding="utf-8") as f:
        f.write(text + "\n")


# =============================================================================== presets dump
def run_presets(args):
    outdir = args.outdir or os.getcwd()
    os.makedirs(outdir, exist_ok=True)
    files = {f"preset_color_{k}.json": v for k, v in COLOR_PRESETS.items()}
    files["preset_bw_BaTiO3.json"] = BW_PRESET
    for name, data in files.items():
        p = os.path.join(outdir, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print(f"wrote {p}")


# =============================================================================== main
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="permittivity-vs-temperature plot digitizer (color + black-and-white)")
    sub = ap.add_subparsers(dest="mode", required=True)

    pc = sub.add_parser("color", help="colour plot: peak / room-T / min values per curve")
    pc.add_argument("image")
    g = pc.add_mutually_exclusive_group()
    g.add_argument("--preset", choices=sorted(COLOR_PRESETS), default="ba_sr")
    g.add_argument("--config", help="JSON config file (see the header of this file)")
    pc.add_argument("--outdir", help="where results/overlay are written (default: next to the image)")

    pb = sub.add_parser("bw", help="black-and-white plot: guide-assisted tracing -> Excel")
    pb.add_argument("--config", help="JSON config file (default: built-in BaTiO3 preset)")
    pb.add_argument("--images", help="folder with the images named in the config (default: bw_test next to this file)")
    pb.add_argument("--outdir", help="where the Excel file and check images are written (default: --images)")

    pt = sub.add_parser("ticks", help="find plot frames and axis tick pixels -> report, check image, bw config draft")
    pt.add_argument("image")
    pt.add_argument("--box", action="append", help="frame given by hand: top,bottom,left,right (repeat for more panels)")
    pt.add_argument("--thr", type=int, default=170, help="gray level below which a tick pixel counts as dark (default 170)")
    pt.add_argument("--outdir", help="where the report/check image/config draft are written (default: next to the image)")

    pp = sub.add_parser("presets", help="write the built-in presets as JSON files (templates for new plots)")
    pp.add_argument("--outdir")

    args = ap.parse_args()
    {"color": run_color, "bw": run_bw, "ticks": run_ticks, "presets": run_presets}[args.mode](args)


if __name__ == "__main__":
    main()
