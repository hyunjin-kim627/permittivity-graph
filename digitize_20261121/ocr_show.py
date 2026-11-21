import json

d = json.load(open(r"C:\Users\user\AppData\Local\Temp\opencode\digitize_20261121\fig5_ocr.json", encoding="utf-8"))
for o in d:
    if o["score"] >= 0.7:
        print(f"{o['cy']:6.1f} {o['cx']:6.1f} {o['score']:.2f} {o['text']}")
