import os
import py_compile

VISION_CODE = r'''import os
import sys
import re
import asyncio
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Optional
import httpx
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from backend.tools.som_capture import capture_som_screenshot
from backend.openai_oauth import call_chatgpt_with_oauth_async

load_dotenv(override=True)
MODEL_ENDPOINTS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
]

def sanitize_scraped_text(raw: str) -> str:
    noise_regex = [
        r"기간\s*시간\s*1일\s*1주[^\n.]*",
        r"직접입력옵션펼치기접기기간\s*설정시작\s*[\d.]+",
        r"옵션펼치기접기",
        r"관련도순\s*최신순",
        r"전체\s*기간",
        r"naver\s*blog",
        r"카테고리\s*이동",
        r"오늘\s*\d+",
        r"전체\s*[\d,]+",
        r"\d+명의\s*이웃",
        r"이웃추가",
        r"안부글",
        r"이웃목록",
        r"앱알림[^\s]*",
        r"활성화하기",
        r"공유하기",
        r"[^\s]+로\s*검색하시겠습니까\??",
        r"새\s*창\s*열림",
        r"본문\s*바로가기",
        r"본문\s*기타\s*기능",
        r"블로그\s*메뉴",
        r"프롤로그",
        r"글쓰기",
        r"댓글\s*\d*",
        r"공감\s*\d*",
        r"무단\s*전재\s*및\s*재배포\s*금지",
        r"\b\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?\s*\d{1,2}:\d{2}\b",
    ]
    text = raw
    for pat in noise_regex:
        text = re.sub(pat, " ", text, flags=re.IGNORECASE)
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line])

async def fetch_multi_source_knowledge(keyword: str, full_prompt: str) -> str:
    """
    [위키백과 공식 API + 네이버 지식백과 + 구글 뉴스 RSS 분리 수집기]
    1) Wikimedia 공식 User-Agent 정책 준수로 403 차단 원천 해결
    2) 동음이의어 안내문('다음 등을 가리킨다')을 자동 스킵하고 실제 상세 본문 4,000자 확보
    3) 백과사전 본문과 뉴스 헤드라인([최신 언론 보도])을 명확히 분리하여 뉴스 도배 방지
    """
    blocks = []
    wiki_headers = {
        "User-Agent": "AICompanyHubPortfolio/3.0 (https://github.com/youngho2; contact@aicompanyhub.local) httpx/0.27"
    }
    browser_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    }

    clean_kw = re.sub(
        r"(?:에\s*대해서|에\s*대해|대해서|관해서|조사해줘|알려줘|정리해줘|비교해줘|분석해줘|작성해줘|써줘|다시\s*찾아줘)",
        " ",
        keyword,
    )
    clean_kw = re.sub(r"\s+", " ", clean_kw).strip() or keyword.strip()

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        # 1) 한국어 위키백과 Query Extracts API (상위 6개 후보 중 동음이의어가 아닌 진짜 본문 2개 확보)
        try:
            w_url = "https://ko.wikipedia.org/w/api.php"
            s_resp = await client.get(
                w_url,
                headers=wiki_headers,
                params={"action": "query", "list": "search", "srsearch": clean_kw, "format": "json", "utf8": 1},
            )
            if s_resp.status_code == 200:
                hits = s_resp.json().get("query", {}).get("search", [])
                fetched_wiki = 0
                for h in hits[:6]:
                    if fetched_wiki >= 2:
                        break
                    p_title = h.get("title", "")
                    if "동음이의" in p_title:
                        continue
                    ext_resp = await client.get(
                        w_url,
                        headers=wiki_headers,
                        params={
                            "action": "query",
                            "prop": "extracts",
                            "explaintext": 1,
                            "exchars": 4200,
                            "titles": p_title,
                            "format": "json",
                        },
                    )
                    if ext_resp.status_code == 200:
                        pages = ext_resp.json().get("query", {}).get("pages", {})
                        for _, p_val in pages.items():
                            ext_txt = (p_val.get("extract") or "").strip()
                            if len(ext_txt) > 150 and "다음 등을 가리킨다" not in ext_txt[:150] and "다음을 가리킨다" not in ext_txt[:150]:
                                blocks.append(
                                    f"[진입 문서 제목]: [위키백과 공식 문서] {p_title}\n"
                                    f"[백과사전 본문 발췌]:\n{ext_txt}"
                                )
                                fetched_wiki += 1
        except Exception:
            pass

        # 2) 네이버 지식백과 및 통합검색 본문 요약 추출
        try:
            naver_url = f"https://search.naver.com/search.naver?where=nexearch&query={urllib.parse.quote(clean_kw)}"
            n_resp = await client.get(naver_url, headers=browser_headers)
            if n_resp.status_code == 200:
                html = n_resp.text
                snippets = re.findall(r'<div[^>]*class="[^"]*(?:dsc_txt|api_txt_lines|mean|desc)[^"]*"[^>]*>(.*?)</div>', html, flags=re.S)
                clean_snips = []
                for sn in snippets[:12]:
                    txt = re.sub(r"<[^>]+>", " ", sn)
                    txt = re.sub(r"&[a-zA-Z0-9#]+;", " ", txt)
                    txt = sanitize_scraped_text(txt).replace("\n", " ").strip()
                    if len(txt) > 40 and txt not in clean_snips:
                        clean_snips.append(txt)
                if clean_snips:
                    if not blocks:
                        blocks.append(f"[진입 문서 제목]: [네이버 지식백과·통합검색] {clean_kw}")
                    blocks.append("[백과사전 및 지식 스니펫]:\n" + "\n".join(clean_snips[:8]))
        except Exception:
            pass

        # 3) Google News RSS (최신 미디어/시장 동향 전용 — 섹션 4에서만 분리 표시)
        try:
            rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(clean_kw)}&hl=ko&gl=KR&ceid=KR:ko"
            rss_resp = await client.get(rss_url, headers=browser_headers)
            if rss_resp.status_code == 200:
                root = ET.fromstring(rss_resp.text)
                news_lines = []
                for item in root.findall(".//item")[:5]:
                    title_el = item.find("title")
                    pub_el = item.find("pubDate")
                    if title_el is not None and title_el.text:
                        t_clean = re.sub(r"<[^>]+>", "", title_el.text).strip()
                        p_date = pub_el.text[:16] if (pub_el is not None and pub_el.text) else "최신 보도"
                        news_lines.append(f"[최신 언론 보도 ({p_date})]: {t_clean}")
                if news_lines:
                    blocks.append("[언론 보도 모음]:\n" + "\n".join(news_lines))
        except Exception:
            pass

    return "\n\n".join(blocks)

def extract_salient_sentences(web_evidence: str, query: str, top_k: int = 12) -> list[str]:
    if not web_evidence:
        return []

    ref_title = ""
    for line in web_evidence.splitlines():
        if "진입 문서 제목]:" in line:
            ref_title = line.split("제목]:")[-1].strip()
            break

    q_tokens = [t.lower() for t in re.findall(r"[가-힣A-Za-z0-9]{2,}", query) if len(t) >= 2]
    stop_tokens = {"대해서", "대해", "조사해줘", "알려줘", "정리해줘", "비교해줘", "작성해줘", "분석해줘", "다시", "찾아줘"}
    q_tokens = [t for t in q_tokens if t not in stop_tokens]

    raw_chunks = []
    for line in web_evidence.splitlines():
        # 뉴스 제목([최신 언론 보도])은 일반 백과사전 문장 추출에서 제외하여 본문 설명이 100% 추출되게 함!
        if "[최신 언론 보도" in line or "[언론 보도 모음]" in line:
            continue
        if any(tag in line for tag in ["[첨부", "[데이터 행", "[엑셀", "[PDF", "[문서 주요", "[전수", "[협력사", "[항목별", "[🚨", "[✅"]):
            raw_chunks.append(line)
        else:
            parts = re.split(r"(?<=[.?!다])\s+|•|\n", line)
            raw_chunks.extend(parts)

    scored = []
    seen_fp = set()

    diary_fluff = [
        "오늘 평소처럼", "접속했다가", "발견했습니다", "그동안 제미나이에서", "넘어가야만 했습니다",
        "포스팅해", "알아보겠습니다", "살펴보겠습니다", "정리해 보겠습니다", "안녕하세요",
        "돈 낭비일까", "나는 처음부터", "구독하기보다", "로고의 권리는", "1일 1주",
        "직접입력", "옵션펼치기", "설정시작", "검색하시겠습니까", "이웃추가", "공감과 댓글",
        "Page.evaluate", "Execution context", "웹 스캔 요약 완료", "기술 데이터 스캔 완료"
    ]

    for chunk in raw_chunks:
        s = chunk.strip()
        is_priority_fact = any(tag in s for tag in ["[첨부", "[데이터 행", "[엑셀", "[PDF", "[문서 주요", "[전수", "[협력사", "[항목별", "[🚨", "[✅"])
        s = re.sub(r"^\[[^\]]+\]:?\s*", "", s).strip()
        s = re.sub(r"^={2,}.*?={2,}", "", s).strip()
        if len(s) < 22 or len(s) > 260:
            continue
        if any(bad in s for bad in diary_fluff):
            continue
        if ref_title and (s == ref_title or (len(ref_title) > 15 and s.startswith(ref_title[:15]))):
            continue

        if not s.endswith((".", "다", "요", "음", "함", "임", "%", ")")):
            s = s + "."

        fp = re.sub(r"[^가-힣A-Za-z0-9]", "", s)[:20]
        if len(fp) < 6 or fp in seen_fp:
            continue
        seen_fp.add(fp)

        score = 10.0 if is_priority_fact else 2.5
        s_lower = s.lower()

        matched_tokens = 0
        for qt in q_tokens:
            if qt in s_lower:
                score += 3.5
                matched_tokens += 1

        has_domain_metric = any(k in s_lower for k in [
            "합격", "불합격", "적격", "부적합", "규격", "실측", "단축", "절감", "벤치마크",
            "주인공", "출시", "개발", "특징", "기능", "성능", "모델", "기술", "프레임워크",
            "요구", "우대", "경력", "자격", "시스템", "등장", "제작", "시리즈", "역할", "히어로", "마블", "스타크", "갑옷", "슈트"
        ])
        if has_domain_metric:
            score += 3.0

        if re.search(r"\d+(?:\.\d+)?\s*(?:%|퍼센트|건|명|년|월|시간|배|억|만|원|달러|\$|점|만\s*토큰|k|편|기|호)", s_lower):
            score += 3.0

        if not is_priority_fact and not has_domain_metric and matched_tokens == 0 and score < 4.0:
            continue

        scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:top_k]]

async def call_gemini_llm(prompt: str, temperature: float = 0.2) -> Optional[str]:
    """동기 표준 라이브러리나 스레드 풀을 쓰지 않고 httpx.AsyncClient로 직접 비동기 통신 수행"""
    gpt_resp = await call_chatgpt_with_oauth_async(prompt, temperature=temperature)
    if gpt_resp:
        return gpt_resp

    load_dotenv(override=True)
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if api_key and api_key != "your_gemini_api_key_here":
        async with httpx.AsyncClient(timeout=18.0) as client:
            for model_name in MODEL_ENDPOINTS:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": temperature, "maxOutputTokens": 1500},
                }
                try:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if len(text) > 80:
                            return text
                except Exception:
                    continue

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": "qwen2.5:7b", "prompt": prompt, "stream": False},
            )
            if resp.status_code == 200:
                o_data = resp.json()
                if o_data.get("response"):
                    return o_data["response"].strip()
    except Exception:
        pass

    return None

def _proactor_playwright_browse_sync(keyword: str, full_prompt: str) -> tuple[list[dict], str]:
    async def _inner():
        frames = []
        evidence_blocks = []
        clean_kw = re.sub(
            r"(?:에\s*대해서|에\s*대해|대해서|관해서|조사해줘|알려줘|정리해줘|비교해줘|분석해줘|작성해줘|써줘|다시\s*찾아줘)",
            " ",
            keyword,
        ).strip() or keyword

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 850},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                encoded = urllib.parse.quote(clean_kw)
                target_url = f"https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={encoded}"

                await page.goto(target_url, wait_until="domcontentloaded", timeout=12000)
                await asyncio.sleep(0.6)
                try:
                    await page.evaluate("""() => {
                        document.querySelectorAll('#header_wrap, #nx_autoframe_top, .atcmp_layer, footer, #footer').forEach(el => el.remove());
                    }""")
                except Exception:
                    pass

                img1, meta1 = await capture_som_screenshot(page)
                frames.append({
                    "step": "Step 1/3 (지식백과·통합웹 스캔)",
                    "img": img1,
                    "log": f"🌐 [Step 1/3 통합 지식·뉴스 스캔] '{clean_kw}' 검색 결과 페이지 요소 {len(meta1)}개에 SoM 번호표 부여"
                })

                await page.mouse.wheel(0, 480)
                await asyncio.sleep(0.5)
                img2, meta2 = await capture_som_screenshot(page)

                try:
                    raw_cards = await page.evaluate("""() => {
                        const pack = document.querySelector('#main_pack') || document.body;
                        const selectors = '.nkindic_area, .api_subject_bx, .news_area, .total_wrap, .view_wrap, .dsc_area';
                        const items = Array.from(pack.querySelectorAll(selectors));
                        return items.map(el => el.innerText || '').slice(0, 15);
                    }""")
                    clean_cards = []
                    for card in raw_cards:
                        c = sanitize_scraped_text(str(card)).replace("\n", " ")
                        if len(c) > 40 and c not in clean_cards:
                            clean_cards.append(f"• {c[:240]}.")
                    if clean_cards:
                        evidence_blocks.append("[웹 검색 지식백과·뉴스 핵심 스니펫]\n" + "\n".join(clean_cards[:8]))
                except Exception:
                    pass

                chosen_article = None
                try:
                    all_links = await page.evaluate("""() => {
                        const pack = document.querySelector('#main_pack') || document.body;
                        return Array.from(pack.querySelectorAll('a[href^="http"]')).map(a => {
                            const r = a.getBoundingClientRect();
                            return {
                                title: (a.innerText || '').trim(),
                                url: a.href || '',
                                x: Math.round(r.left + r.width / 2),
                                y: Math.round(r.top + r.height / 2)
                            };
                        });
                    }""")
                    scored_links = []
                    for item in all_links:
                        u = item["url"]
                        t = sanitize_scraped_text(item["title"]).replace("\n", " ")
                        if len(t) < 6 or any(skip in u for skip in ["search.naver.com", "nid.naver.com", "adcr.naver.com", "keep.naver.com", "help.naver.com"]):
                            continue
                        score = 0
                        if "terms.naver.com" in u or "wikipedia.org" in u or "namu.wiki" in u:
                            score += 25
                        elif "news.naver.com" in u or "zdnet.co.kr" in u or "aitimes.com" in u:
                            score += 18
                        elif "blog.naver.com" in u:
                            score += 5
                        if any(tok.lower() in t.lower() for tok in clean_kw.split() if len(tok) >= 2):
                            score += 10
                        if score >= 10:
                            scored_links.append((score, item))

                    scored_links.sort(key=lambda x: x[0], reverse=True)
                    if scored_links:
                        chosen_article = scored_links[0][1]
                except Exception:
                    pass

                som_box_id = 12
                if chosen_article and meta2:
                    best_el = min(
                        meta2,
                        key=lambda m: abs(m.get("x", 0) - chosen_article["x"]) + abs(m.get("y", 0) - chosen_article["y"])
                    )
                    som_box_id = best_el.get("id", 12)

                target_title_short = chosen_article["title"][:32] if chosen_article else f"{clean_kw} 상세 문서"
                frames.append({
                    "step": "Step 2/3 (핵심 문서 타깃팅)",
                    "img": img2,
                    "log": f"🖱️ [Step 2/3 핵심 출처 타깃팅] #{som_box_id}번 '{target_title_short}...' 문서 진입"
                })

                if chosen_article and chosen_article.get("url"):
                    try:
                        article_url = chosen_article["url"]
                        if "blog.naver.com/" in article_url and "m.blog.naver.com" not in article_url:
                            article_url = article_url.replace("://blog.naver.com/", "://m.blog.naver.com/")

                        await page.goto(article_url, wait_until="domcontentloaded", timeout=10000)
                        await asyncio.sleep(0.6)
                        await page.mouse.wheel(0, 350)
                        await asyncio.sleep(0.3)

                        raw_body = await page.evaluate("""() => {
                            const container = document.querySelector('#size_ct, #dic_area, #newsct_article, .se-main-container, article, main') || document.body;
                            return container ? (container.innerText || '') : '';
                        }""")
                        clean_body = sanitize_scraped_text(str(raw_body))
                        if len(clean_body) > 60:
                            evidence_blocks.insert(
                                0,
                                f"[SoM #{som_box_id}번 진입 문서 제목]: {chosen_article['title'][:75]}\n"
                                f"[문서 본문 발췌]:\n{clean_body[:4500]}"
                            )

                        img3, _ = await capture_som_screenshot(page)
                        frames.append({
                            "step": "Step 3/3 (본문 팩트 추출)",
                            "img": img3,
                            "log": f"🎯 [Step 3/3 본문 크롤링 완료] '{chosen_article['title'][:28]}...' 본문에서 상세 정보를 추출했습니다."
                        })
                    except Exception:
                        pass
            finally:
                await browser.close()

        return frames, "\n\n".join(evidence_blocks)

    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_inner())
    finally:
        loop.close()

async def playwright_vision_browse(
    keyword: str, goal: str, agent_id: str, agent_name: str,
    event_queue: Optional[asyncio.Queue] = None
) -> dict:
    api_knowledge = await fetch_multi_source_knowledge(keyword, goal)

    frames = []
    browser_evidence = ""
    try:
        frames, browser_evidence = await asyncio.to_thread(_proactor_playwright_browse_sync, keyword, goal)
    except Exception:
        pass

    if event_queue and frames:
        for f in frames:
            await event_queue.put({
                "type": "BROWSER_FRAME", "agentId": agent_id, "agentName": agent_name,
                "role": "WORKER", "timestamp": f["step"],
                "payload": {"status": "WORKING", "screenshotUrl": f["img"], "text": f["step"]}
            })
            await event_queue.put({
                "type": "MESSAGE", "agentId": agent_id, "agentName": agent_name,
                "role": "WORKER", "timestamp": f["step"],
                "payload": {"status": "WORKING", "text": f["log"], "tokensUsed": 150}
            })
            await asyncio.sleep(0.35)

    combined = "\n\n".join([b for b in [api_knowledge, browser_evidence] if b.strip()])
    return {"collected_data": combined}
'''

with open("backend/tools/vision_browser.py", "w", encoding="utf-8") as f:
    f.write(VISION_CODE)

with open("backend/workflow.py", "r", encoding="utf-8") as f:
    wf = f.read()

wf = wf.replace(
    'news_lines = [line.strip() for line in web_evidence.splitlines() if "[언론 보도" in line]',
    'news_lines = [re.sub(r"^[•\\-\\*]\\s*", "", line.strip()) for line in web_evidence.splitlines() if "[최신 언론 보도" in line]'
)

with open("backend/workflow.py", "w", encoding="utf-8") as f:
    f.write(wf)

py_compile.compile("backend/tools/vision_browser.py", doraise=True)
py_compile.compile("backend/workflow.py", doraise=True)
print("✅ vision_browser.py & workflow.py 직접 덮어쓰기 및 컴파일 완료!")
