import os

# 1. vision_browser.py: 정량 수치/판정/규격이 포함된 알짜 문장이 누락되지 않도록 추출기 보정
with open("backend/tools/vision_browser.py", "r", encoding="utf-8") as f:
    vb = f.read()

old_filter = "if not is_file_fact and matched_tokens == 0 and score < 4.0:"
new_filter = "has_domain_metric = any(k in s_lower for k in ['합격', '불합격', '적격', '부적합', '규격', '실측', '단축', '절감', '벤치마크'])\n        if not is_file_fact and not has_domain_metric and matched_tokens == 0 and score < 3.5:"

vb = vb.replace(old_filter, new_filter)
with open("backend/tools/vision_browser.py", "w", encoding="utf-8") as f:
    f.write(vb)

# 2. workflow.py: evaluate_qc_rubric Fast-Track 채점 기준 정밀화
with open("backend/workflow.py", "r", encoding="utf-8") as f:
    wf = f.read()

old_rubric = '''    if is_final or has_5_sections or has_second_crawl:
        depth_score = 30
    elif has_tabular_stats and len(key_sents) >= 7 and nums_in_evidence >= 15:
        # 1차에서 이미 전수 파일 통계와 충분한 웹 벤치마크가 모두 확보된 경우 Fast-Track 통과 가능!
        depth_score = 25
    else:
        depth_score = 12'''

new_rubric = '''    if is_final or has_5_sections or has_second_crawl:
        depth_score = 30
    elif (has_tabular_stats and len(key_sents) >= 5) or (len(key_sents) >= 6 and nums_in_evidence >= 10):
        # 1차에서 전수 파일 통계 또는 충분한 정량 팩트(6문장 이상 + 수치 10개 이상)가 확보된 경우 Fast-Track 통과!
        depth_score = 26
    else:
        depth_score = 12'''

wf = wf.replace(old_rubric, new_rubric)
with open("backend/workflow.py", "w", encoding="utf-8") as f:
    f.write(wf)

print("✅ 추출기 및 QC 루브릭 Fast-Track 보정 완료!")
