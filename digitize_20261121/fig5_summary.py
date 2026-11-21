from openpyxl import load_workbook

p = r"C:\Users\user\AppData\Local\Temp\opencode\digitize_20261121\fig5_전체_결과.xlsx"
wb = load_workbook(p, data_only=True)
for ws in wb.worksheets:
    if ws.title == "설명":
        continue
    print(ws.title)
    for row in ws.iter_rows(min_row=2, values_only=True):
        print("  ", row[0], "peak", row[1], "@", row[5], "C", "room", row[7])
