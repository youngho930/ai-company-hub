with open("backend/tools/vision_browser.py", "r", encoding="utf-8") as f:
    code = f.read()

old_func = '''async def call_gemini_llm(prompt: str, temperature: float = 0.2) -> Optional[str]:
    """실제 Gemini 모델을 호출하되, 429 한도 초과 시 짧은 대기 후 1회 재시도"""
    load_dotenv(override=True)
    llm = ChatGoogleGenerativeAI(model=ACTIVE_MODEL, temperature=temperature, max_retries=0, timeout=22)
    for attempt in range(2):
        try:
            resp = await llm.ainvoke(prompt)
            content = resp.content if isinstance(resp.content, str) else str(resp.content)
            if content and len(content.strip()) > 40:
                return content.strip()
        except Exception as e:
            err_str = str(e)
            if ("429" in err_str or "ResourceExhausted" in err_str) and attempt == 0:
                await asyncio.sleep(4.0)
                continue
            break
    return None'''

new_func = '''def _direct_rest_gemini(prompt: str, temperature: float = 0.2) -> Optional[str]:
    """LangChain의 숨겨진 5회 재시도(쿼터 증발) 버그를 원천 차단하는 순수 REST API 호출기 (정확히 1회만 호출)"""
    import json
    import urllib.request
    load_dotenv(override=True)
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{ACTIVE_MODEL}:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 900}
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=18) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"[Direct REST Info] API 응답 대기 또는 쿨타임 폴백 전환: {str(e)[:60]}")
        return None

async def call_gemini_llm(prompt: str, temperature: float = 0.2) -> Optional[str]:
    return await asyncio.to_thread(_direct_rest_gemini, prompt, temperature)'''

if old_func in code:
    code = code.replace(old_func, new_func)
    with open("backend/tools/vision_browser.py", "w", encoding="utf-8") as f:
        f.write(code)
    print("✅ LangChain 재시도 폭주 제거 및 Direct REST 연동 완료!")
else:
    print("ℹ️ 이미 적용되어 있거나 함수 시그니처를 확인해 주세요.")