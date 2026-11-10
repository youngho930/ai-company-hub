with open("backend/tools/vision_browser.py", "r", encoding="utf-8") as f:
    vb = f.read()

vb = vb.replace("동기 urllib.request나", "동기 표준 라이브러리나")
with open("backend/tools/vision_browser.py", "w", encoding="utf-8") as f:
    f.write(vb)

print("✅ 주석 클린업 완료!")
