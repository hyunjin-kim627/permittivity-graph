"""Trace the black-and-white BaTiO3 figures and write the data to an Excel workbook + check overlays."""
import sys; sys.path.insert(0, '.')
import numpy as np
from PIL import Image, ImageDraw
from openpyxl import Workbook
from openpyxl.chart import ScatterChart, Reference, Series
from openpyxl.styles import Font, Alignment
from calib import fits
from trace import trace
from curves_fig2 import FIG2A, FIG2B, FIG2C
from curves_fig1 import FIG1

JOBS = [  # sheet, panel, curves, k, T step (C), title
    ('Fig1', 'fig1', FIG1, 4, 2.0, 'Fig.1 grain-size BaTiO3, -150..190 C'),
    ('Fig2a', 'fig2a', FIG2A, 3, 0.5, 'Fig.2(a) cubic-tetragonal, 90..140 C'),
    ('Fig2b', 'fig2b', FIG2B, 3, 1.0, 'Fig.2(b) tetragonal-orthorhombic, -20..40 C'),
    ('Fig2c', 'fig2c', FIG2C, 3, 1.0, 'Fig.2(c) orthorhombic-rhombohedral, -120..-55 C'),
]
NOTE = {
    'curve A (1.5um)': '라벨로 확인',
    'curve B': '2.2um로 추정 (입자 클수록 eps 작아지는 경향 + 라벨 위치)',
    'curve C': '3.0um로 추정',
    'curve D': '13um로 추정',
    'above Tc (all curves)': '모든 곡선이 겹치는 구간 (구분 불가, 공통값)',
    'above Tc (all curves coincide)': '모든 곡선이 겹치는 구간 (구분 불가, 공통값)',
}
COL = [(255,0,0),(0,170,0),(0,140,255),(220,0,220),(255,140,0),(0,190,190),(120,60,255)]

def resample(out, step):
    """x-mode points -> values at round T; y-mode points (steep parts) -> every ~0.25e3 of eps."""
    xs = sorted([o for o in out if o[4] == 'x'], key=lambda o: o[0])
    ys = sorted([o for o in out if o[4] == 'y'], key=lambda o: o[1])
    rows = []
    if xs:
        T = np.array([o[0] for o in xs]); E = np.array([o[1] for o in xs])
        for t in np.arange(np.ceil(T[0] / step) * step, T[-1] + 1e-9, step):
            j = np.searchsorted(T, t)
            near = min(abs(T[max(j-1, 0)] - t), abs(T[min(j, len(T)-1)] - t))
            if near <= max(step / 2, 0.6):
                rows.append((round(float(t), 2), round(float(np.interp(t, T, E))), '열 단위 추적'))
    if ys:
        last = -1e9
        for o in ys:
            if o[1] - last >= 250:
                rows.append((round(float(o[0]), 2), round(float(o[1])), '급경사: 행 단위 추적'))
                last = o[1]
    return rows

wb = Workbook(); info = wb.active; info.title = '설명'
summary = []
for sheet, panel, curves, k, step, title in JOBS:
    c = fits(panel); t, b, l, r = c['box']
    ws = wb.create_sheet(sheet)
    ws.append([title]); ws['A1'].font = Font(bold=True)
    ws.append(['곡선', 'T (°C)', '유전상수 ε', '읽은 방식', '비고'])
    for cell in ws[2]: cell.font = Font(bold=True)
    im = Image.open(c['file']).convert('RGB').crop((l-2, t-2, r+3, b+3))
    im = im.resize((im.width * 4, im.height * 4), Image.NEAREST); d = ImageDraw.Draw(im)
    chart = ScatterChart(); chart.title = title; chart.style = 13
    chart.x_axis.title = 'Temperature (°C)'; chart.y_axis.title = 'Dielectric constant'
    chart.height, chart.width = 12, 20
    for i, (cn, cv) in enumerate(curves.items()):
        _, out = trace(panel, cv, k=k)
        data = resample(out, step)
        r0 = ws.max_row + 1
        for T, E, how in data:
            ws.append([cn, T, E, how, NOTE.get(cn, '')])
        r1 = ws.max_row
        s = Series(Reference(ws, min_col=3, min_row=r0, max_row=r1), Reference(ws, min_col=2, min_row=r0, max_row=r1), title=cn)
        s.marker.symbol = 'circle'; s.marker.size = 3; s.smooth = False
        chart.series.append(s)
        pk = max(data, key=lambda x: x[1])
        summary.append([sheet, cn, len(data), min(x[0] for x in data), max(x[0] for x in data), pk[1], pk[0]])
        for T, E, x, y, m in out:
            X = (x - (l-2)) * 4 + 2; Y = (y - (t-2)) * 4 + 2
            d.rectangle([X-1, Y-1, X+1, Y+1], fill=COL[i % len(COL)])
        X = 8; Y = 8 + 18 * i
        d.rectangle([X, Y, X+12, Y+12], fill=COL[i % len(COL)]); d.text((X+18, Y), cn, fill=COL[i % len(COL)])
    for col, w in zip('ABCDE', (30, 10, 12, 20, 50)): ws.column_dimensions[col].width = w
    ws.add_chart(chart, 'G3')
    im.save(f'검증_{sheet}.png')

info.append(['흑백 BaTiO3 유전상수-온도 그래프 디지타이징 결과']); info['A1'].font = Font(bold=True, size=13)
for line in [
    '',
    '원본: fig1_BaTiO3_grainsize.png (Fig.1, 입자 크기별 고순도 BaTiO3 세라믹), fig2_BaTiO3_3transitions.png (Fig.2 a,b,c, 1.1um vs 53um, 세 상전이 근처)',
    '',
    '방법',
    ' 1) 축 보정: 프레임 안쪽 짧은 눈금을 픽셀에서 자동으로 찾아, 눈금 값과 1차식으로 맞춤 (맞춤 잔차 x ≤0.18 °C, y ≤10 ε)',
    ' 2) 곡선 추적: 곡선마다 대략적인 경로(가이드)를 눈으로 지정 → 각 열(급경사 구간은 각 행)에서 가이드에 가장 가까운 검은 선 픽셀의 중심을 읽음',
    ' 3) 정리: 일정 온도 간격으로 보간해 표로 저장 (Fig1 2 °C, Fig2a 0.5 °C, Fig2b·c 1 °C). 급경사 구간은 ε 약 250 간격',
    ' 4) 검증: 같은 폴더의 검증_*.png 에 읽은 점을 색깔별로 원본 위에 그려 두었음 → 눈으로 확인 권장',
    '',
    '값은 측정점(마커)이 아니라 마커를 잇는 선을 따라 읽은 값입니다. 측정점 자체가 필요하면 마커 위치를 따로 읽어야 합니다.',
    '',
    '읽기 오차 (선 두께 ±1~2 px 기준, 대략)',
    ' Fig1 : 1 px = 0.97 °C, 24.6 ε  → 약 ±2 °C, ±50 ε',
    ' Fig2a: 1 px = 0.17 °C, 21.0 ε  → 약 ±0.3 °C, ±40 ε',
    ' Fig2b: 1 px = 0.21 °C, 21.2 ε  → 약 ±0.4 °C, ±40 ε',
    ' Fig2c: 1 px = 0.21 °C, 21.3 ε  → 약 ±0.4 °C, ±40 ε',
    '',
    '주의',
    ' - cooling = 실선·빈 마커(← 화살표), heating = 점선·채운 마커(→ 화살표)',
    ' - Fig1: 1.1um, 53um만 전 구간 분리 가능. 1.5/2.2/3.0/13um 곡선은 -140~20 °C와 Tc 근처에서 서로 겹쳐 구분 불가 →',
    '         구분되는 26~88 °C 구간만 curve A~D로 읽음. A=1.5um(라벨 확인), B·C·D=2.2/3.0/13um는 추정.',
    ' - Fig1 53um 곡선은 -135~-90 °C에서 다른 곡선(C 또는 D)과 겹쳐 있어 그 구간 값은 두 곡선 공통값일 수 있음',
    ' - Tc(약 120~125 °C) 위쪽은 모든 곡선이 겹쳐 하나의 공통 곡선으로 읽음',
    ' - Fig2a 꼭대기(ε > 약 10000) 부근은 곡선 4개가 몇 픽셀 안에 몰려 있어 피크 값 오차가 더 큼',
]:
    info.append([line])
info.append([]); info.append(['요약: 시트', '곡선', '점 개수', 'T 최소', 'T 최대', '최대 ε', '최대 ε 온도'])
for cell in info[info.max_row]: cell.font = Font(bold=True)
for s in summary: info.append(s)
info.column_dimensions['A'].width = 14; info.column_dimensions['B'].width = 32
wb.save('BaTiO3_흑백그래프_디지타이징.xlsx')
for s in summary: print(s)
