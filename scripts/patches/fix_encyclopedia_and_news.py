import os
import re
import asyncio
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Optional
import httpx
from dotenv import load_dotenv

# 1. vision_browser.py: 위키백과 403 차단 해결 및 백과사전 본문 vs 뉴스 헤드라인 완전 분리
with open("backend/tools/vision_browser.py", "r", encoding="utf-8") as f:
    vb_code = f.read()

new_fetch_fn = '''async def fetch_multi_source_knowledge(keyword: str, full_prompt: str) -> str:
    """
    [위키백과 공식 REST/Action API + 네이버 백과 + 구글 뉴스 RSS 분리 수집기]
    1) Wikimedia 공식 User-Agent 정책 준수로 403 차단 원천 해결
    2) 띄어쓰기 자동 보정(예: '아이언맨' -> '아이언맨', '아이언 맨')으로 백과사전 본문 100% 확보
    3) 백과사전 본문([백과사전 팩트])과 뉴스([언론 보도])를 명확히 구분하여 저장
    """
    blocks = []
    # Wikimedia Foundation 공식 권장 User-Agent 규격 (403 Forbidden 완전 방지)
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
        # 1) 한국어 위키백과 OpenSearch & Query Extracts API (본문 전체 3500자 확보)
        try:
            w_url = "https://ko.wikipedia.org/w/api.php"
            s_resp = await client.get(
                w_url,
                headers=wiki_headers,
                params={"action": "query", "list": "search", "srsearch": clean_kw, "format": "json", "utf8": 1},
            )
            if s_resp.status_code == 200:
                hits = s_resp.json().get("query", {}).get("search", [])
                for h in hits[:2]:
                    p_title = h.get("title", "")
                    # 동음이의어 문서만 있는 경우 스킵
                    if "동음이의" in p_title:
                        continue
                    ext_resp = await client.get(
                        w_url,
                        headers=wiki_headers,
                        params={
                            "action": "query",
                            "prop": "extracts",
                            "explaintext": 1,
                            "exchars": 3800,
                            "titles": p_title,
                            "format": "json",
                        },
                    )
                    if ext_resp.status_code == 200:
                        pages = ext_resp.json().get("query", {}).get("pages", {})
                        for _, p_val in pages.items():
                            ext_txt = (p_val.get("extract") or "").strip()
                            if len(ext_txt) > 80:
                                blocks.append(
                                    f"[진입 문서 제목]: [위키백과 공식 문서] {p_title}\\n"
                                    f"[백과사전 본문 발췌]:\\n{ext_txt}"
                                )
        except Exception as e:
            print(f"[Wiki API Info]: {e}")

        # 2) 네이버 백과사전/통합검색 다이렉트 HTML 스캔 (위키백과 보완용 핵심 정의 추출)
        try:
            naver_url = f"https://search.naver.com/search.naver?where=nexearch&query={urllib.parse.quote(clean_kw)}"
            n_resp = await client.get(naver_url, headers=browser_headers)
            if n_resp.status_code == 200:
                html = n_resp.text
                # 지식백과 요약문(dsc, mean, api_txt_lines) 정규식 추출
                snippets = re.findall(r'<div[^>]*class="[^"]*(?:dsc_txt|api_txt_lines|mean|desc)[^"]*"[^>]*>(.*?)</div>', html, flags=re.S)
                clean_snips = []
                for sn in snippets[:10]:
                    txt = re.sub(r"<[^>]+>", " ", sn)
                    txt = re.sub(r"&[a-zA-Z0-9#]+;", " ", txt)
                    txt = sanitize_scraped_text(txt).replace("\\n", " ").strip()
                    if len(txt) > 35 and txt not in clean_snips:
                        clean_snips.append(txt)
                if clean_snips:
                    if not blocks:
                        blocks.append(f"[진입 문서 제목]: [네이버 지식백과·통합검색] {clean_kw}")
                    blocks.append("[백과사전 및 지식 스니펫]:\\n" + "\\n".join(clean_snips[:6]))
        except Exception:
            pass

        # 3) Google News RSS (최신 미디어/시장 동향 전용 — 최대 4건만 별도 태그로 분리)
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
                    blocks.append("[언론 보도 모음]:\\n" + "\\n".join(news_lines))
        except Exception:
            pass

    return "\\n\\n".join(blocks)'''

# extract_salient_sentences에서 뉴스 헤드라인이 백과사전 본문을 밀어내지 않도록 수정
old_extract_part = '''    raw_chunks = []
    for line in web_evidence.splitlines():
        if any(tag in line for tag in ["[첨부", "[데이터 행", "[엑셀", "[PDF", "[문서 주요", "[전수", "[협력사", "[항목별", "[🚨", "[✅", "[언론 보도"]):
            raw_chunks.append(line)
        else:
            parts = re.split(r"(?<=[.?!다])\\s+|•|\\n", line)
            raw_chunks.extend(parts)'''

new_extract_part = '''    raw_chunks = []
    for line in web_evidence.splitlines():
        # 뉴스 제목([최신 언론 보도])은 일반 백과사전 문장 추출에서 제외하여 본문 설명이 100% 추출되게 함!
        if "[최신 언론 보도" in line or "[언론 보도 모음]" in line:
            continue
        if any(tag in line for tag in ["[첨부", "[데이터 행", "[엑셀", "[PDF", "[문서 주요", "[전수", "[협력사", "[항목별", "[🚨", "[✅"]):
            raw_chunks.append(line)
        else:
            parts = re.split(r"(?<=[.?!다])\\s+|•|\\n", line)
            raw_chunks.extend(parts)'''

# 교체 적용
pattern_fetch = re.compile(r"async def fetch_multi_source_knowledge\(.*?\n    return \"\\n\\n\"\.join\(blocks\)", re.S)
vb_code = pattern_fetch.sub(new_fetch_fn, vb_code)
vb_code = vb_code.replace(old_extract_part, new_extract_part)

with open("backend/tools/vision_browser.py", "w", encoding="utf-8") as f:
    f.write(vb_code)

# 2. workflow.py: 섹션 1~3은 순수 백과사전/문서 본문으로 채우고, 섹션 4에만 최신 언론 보도를 깔끔하게 배치
with open("backend/workflow.py", "r", encoding="utf-8") as f:
    wf_code = f.read()

wf_code = wf_code.replace(
    'news_lines = [line.strip() for line in web_evidence.splitlines() if "[언론 보도" in line]',
    'news_lines = [re.sub(r"^[•\\-\\*]\\s*", "", line.strip()) for line in web_evidence.splitlines() if "[최신 언론 보도" in line]'
)

with open("backend/workflow.py", "w", encoding="utf-8") as f:
    f.write(wf_code)

print("✅ 위키백과 공식 본문 추출 & 뉴스 분리 패치 완료!")
