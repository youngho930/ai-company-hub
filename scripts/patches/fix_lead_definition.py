with open("backend/tools/vision_browser.py", "r", encoding="utf-8") as f:
    vb = f.read()

# 1) 메인 문서 제목이 검색어와 정확히 일치하면 파생 영화(아이언맨 3 등)를 섞지 않고 메인 문서만 6000자 깊게 추출!
vb = vb.replace(
    "if fetched_wiki >= 2:",
    "if fetched_wiki >= 1:"
)
vb = vb.replace(
    '"exchars": 4200,',
    '"exchars": 6500,'
)

# 2) 백과사전 도입부 첫 문장(핵심 정의문: '~은/는 ~이다')이 연도 숫자에 밀리지 않고 무조건 1순위(핵심 요약)로 뽑히도록 순서 가산점 부여!
old_loop = "    for chunk in raw_chunks:"
new_loop = "    for idx_Pos, chunk in enumerate(raw_chunks):"
vb = vb.replace(old_loop, new_loop)

old_score = "        score = 10.0 if is_priority_fact else 2.5"
new_score = '''        score = 10.0 if is_priority_fact else 2.5
        # 백과사전 맨 앞 도입부(0~4번째 문장)의 핵심 정의문에 최우선 가산점 부여!
        if idx_Pos == 0:
            score += 12.0
        elif idx_Pos <= 3:
            score += 7.0'''
vb = vb.replace(old_score, new_score)

with open("backend/tools/vision_browser.py", "w", encoding="utf-8") as f:
    f.write(vb)

print("✅ 백과사전 도입부 핵심 정의문 1순위 고정 및 메인 문서 집중 패치 완료!")
