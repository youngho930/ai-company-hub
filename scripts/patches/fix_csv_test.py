with open("backend/file_processor.py", "r", encoding="utf-8") as f:
    fp = f.read()

# CSV 디코딩 성공 시 즉시 루프를 탈출(break)하도록 확실히 보장
old_block = '''        if fname_lower.endswith(".csv"):
            text_data = ""
            for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
                try:
                    text_data = content.decode(enc)
                    break
                except Exception:
                    continue'''

new_block = '''        if fname_lower.endswith(".csv"):
            text_data = ""
            for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
                try:
                    text_data = content.decode(enc)
                    if "판정" in text_data or "LOT" in text_data or "," in text_data:
                        break
                except Exception:
                    continue'''

if old_block in fp:
    fp = fp.replace(old_block, new_block)

# '기준규격'에 '규격'이 포함되어 check_idx나 val_idx와 겹치지 않도록 헤더 탐지 조건 정밀화
old_header_loop = '''    for idx, h in enumerate(headers):
        h_low = h.lower()
        if any(k in h_low for k in ["판정", "결과", "합격", "불합격", "status", "result", "judge"]):
            judge_idx = idx
        elif any(k in h_low for k in ["협력사", "거래처", "공급사", "업체", "vendor", "supplier"]):
            vendor_idx = idx
        elif any(k in h_low for k in ["품목", "자재", "모델", "제품", "item", "product"]):
            item_idx = idx
        elif any(k in h_low for k in ["항목", "특성", "check", "parameter"]):
            check_idx = idx
        elif any(k in h_low for k in ["실측", "측정", "결과값", "measured", "value"]):
            val_idx = idx
        elif any(k in h_low for k in ["오차", "편차", "diff", "deviation", "error"]):
            dev_idx = idx'''

new_header_loop = '''    for idx, h in enumerate(headers):
        h_low = h.lower()
        if any(k in h_low for k in ["판정", "합격", "불합격", "status", "judge"]):
            judge_idx = idx
        elif any(k in h_low for k in ["협력사", "거래처", "공급사", "업체", "vendor", "supplier"]):
            vendor_idx = idx
        elif any(k in h_low for k in ["품목", "자재", "모델", "제품", "item", "product"]):
            item_idx = idx
        elif any(k in h_low for k in ["항목", "특성", "check", "parameter"]):
            check_idx = idx
        elif any(k in h_low for k in ["실측", "측정", "결과값", "measured", "value"]):
            val_idx = idx
        elif any(k in h_low for k in ["오차", "편차", "diff", "deviation", "error"]):
            dev_idx = idx'''

fp = fp.replace(old_header_loop, new_header_loop)
with open("backend/file_processor.py", "w", encoding="utf-8") as f:
    f.write(fp)

print("✅ file_processor.py CSV 헤더 및 편차 연산 보정 완료!")
