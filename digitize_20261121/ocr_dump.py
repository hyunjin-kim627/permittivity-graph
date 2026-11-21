import json
from rapidocr_onnxruntime import RapidOCR

image = r"C:\Users\user\OneDrive\문서\유전율_그래프_측정\새 폴더\10.1016_j.jeurceramsoc.2023.01.027_fig5.png"
outpath = r"C:\Users\user\AppData\Local\Temp\opencode\digitize_20261121\fig5_ocr.json"

engine = RapidOCR()
result, elapsed = engine(image)
items = []
for box, text, score in result or []:
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    items.append({
        "text": text,
        "score": round(float(score), 3),
        "box": box,
        "cx": round(sum(xs) / 4, 1),
        "cy": round(sum(ys) / 4, 1),
        "w": round(max(xs) - min(xs), 1),
        "h": round(max(ys) - min(ys), 1),
    })
items.sort(key=lambda o: (o["cy"], o["cx"]))
with open(outpath, "w", encoding="utf-8") as f:
    json.dump(items, f, ensure_ascii=False, indent=1)
print("count", len(items), "elapsed", elapsed)
