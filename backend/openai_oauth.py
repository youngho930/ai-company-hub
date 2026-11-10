import os
import json
import time
import asyncio
from typing import Optional
import httpx
from dotenv import load_dotenv

load_dotenv(override=True)
TOKEN_FILE = os.path.join(os.getcwd(), ".chatgpt-token.json")

def load_chatgpt_token() -> Optional[dict]:
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("access_token"):
            return data
    except Exception:
        pass
    return None

def save_chatgpt_token(token_data: dict) -> None:
    payload = {
        "access_token": token_data.get("access_token", ""),
        "model": token_data.get("model", "gpt-4o-mini"),
        "mode": token_data.get("mode", "ASYNC_HTTPX"),
        "saved_at": int(time.time()),
    }
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def clear_chatgpt_token() -> None:
    if os.path.exists(TOKEN_FILE):
        try:
            os.remove(TOKEN_FILE)
        except Exception:
            pass

async def auto_connect_chatgpt_browser() -> dict:
    """네이티브 비동기 Playwright(async_playwright)를 사용하여 스레드 블로킹 없이 세션 토큰 추출"""
    try:
        from playwright.async_api import async_playwright
        profile_dir = os.path.join(os.getcwd(), ".chatgpt-browser-profile")
        os.makedirs(profile_dir, exist_ok=True)

        extracted_token = ""
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                viewport={"width": 540, "height": 700},
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else await context.new_page()
            try:
                await page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=20000)
            except Exception:
                pass

            for _ in range(90):
                if len(context.pages) == 0 or page.is_closed():
                    break
                try:
                    res = await page.evaluate("""async () => {
                        try {
                            const r = await fetch('/api/auth/session');
                            if (!r.ok) return null;
                            return await r.json();
                        } catch (e) { return null; }
                    }""")
                    if res and isinstance(res, dict) and res.get("accessToken"):
                        extracted_token = res["accessToken"]
                        break
                except Exception:
                    pass
                await asyncio.sleep(1.0)

            try:
                await context.close()
            except Exception:
                pass

        if extracted_token:
            save_chatgpt_token({
                "access_token": extracted_token,
                "model": "gpt-4o-mini",
                "mode": "CHATGPT_WEB_OAUTH"
            })
            return {"status": "OK", "token": extracted_token}
    except Exception as e:
        print(f"[Async Browser Auth Info]: {str(e)[:60]}")

    return {"status": "CANCELLED"}

async def call_chatgpt_with_oauth_async(prompt: str, temperature: float = 0.2) -> Optional[str]:
    """순수 비동기 httpx.AsyncClient를 통한 논블로킹(Non-blocking) OpenAI API 호출"""
    token_info = load_chatgpt_token()
    access_token = (token_info or {}).get("access_token") or os.getenv("OPENAI_API_KEY", "").strip()

    if access_token and access_token.startswith("sk-"):
        model_name = (token_info or {}).get("model", "gpt-4o-mini")
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "당신은 정확한 팩트와 기술 지식을 기반으로 보고서를 작성하는 수석 AI 에이전트입니다."},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": 1100,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["choices"][0]["message"]["content"].strip()
                    if len(text) > 40:
                        return text
        except Exception:
            pass

    return None
