# 🏢 AI Company Hub — Enterprise Multi-Agent Mission Control

> **LangGraph 기반 자율형 멀티 에이전트 오케스트레이션 & 결정론적 데이터 정합(CoA/QC) 및 2.5D 실시간 관제 플랫폼**

단순 질의응답(Chatbot)의 한계를 넘어, 사내 5개 전문 부서(인사·리서치, SW개발, 품질보증·QA, 재무·데이터, 마케팅·전략)의 AI 에이전트들이 역할을 분담해 **웹·문서 크롤링 ➔ 결정론적 통계 연산 ➔ 팀장급 정량 루브릭 검수(QC Gate) ➔ 반려 시 2차 심화 재조사 ➔ 다중 포맷(Word/Excel/PDF) 보고서 발행 및 ERP 연동**을 수행하는 엔터프라이즈 AI 워크플로우 시스템입니다.

---

## ✨ 핵심 엔지니어링 아키텍처 (5 Pillars)

### 1. 비조작(Un-rigged) 동적 QC 루브릭 & 자율 ReAct 재조사 루프 (LangGraph)
* **정량 루브릭 검수 게이트 (85점 기준):** 1차 수집 팩트 밀도(35점), 정량·통계 근거(35점), 교차검증 깊이(30점)를 정량 채점합니다.
* **조건부 분기 (oute_after_qc):** 1차 조사에서 충분한 정량 데이터가 확보되면 재조사 없이 즉시 승인(**Fast-Track**)하고, 기준 미달 시 팀장이 반려(QC_REJECT)하여 부족한 키워드를 보완한 **2차 심화 쿼리로 실제 Playwright 재크롤링**을 수행합니다.

### 2. 결정론적(Deterministic) 전수 데이터 연산 & 자동 규격(Spec) 판정 엔진
* LLM의 산술 환각(Hallucination)을 원천 차단하기 위해 Python(OpenPyXL / CSV) 기반 전수 데이터 연산기를 탑재했습니다.
* **스마트 헤더 탐지:** 현업 엑셀 상단(1~10행)의 결재란·제목 병합 셀을 자동으로 건너뛰고 실제 데이터 헤더 행을 식별합니다.
* **수학적 공차(Tolerance) 자동 판정:** 성적서(CoA)에 합격/불합격 열이 없어도 100 ± 5, 99.5 이상, 20 이하, 95 ~ 105 등의 기준 규격(Spec) 문자열을 정규식으로 해독해 실측치와의 편차 및 적격 여부를 오차 0%로 자동 연산합니다.

### 3. 4중 하이브리드 지식 수집 & Set-of-Mark (SoM) Vision 브라우징
* **다중 출처 교차 수집:** 개인 블로그 노이즈를 배제하고 ① Wikipedia 공식 REST/Action API, ② 네이버 지식백과, ③ Google News 실시간 RSS, ④ Playwright 헤드리스 브라우저를 결합해 할루시네이션 없는 팩트를 수집합니다.
* **SoM 시각적 그라운딩:** 웹 페이지 내 상호작용 요소에 빨간색 번호표(Bounding Box)를 부여하고 실시간 스캔 프레임을 스트리밍합니다.

### 4. 세션 동시성 격리(Session Isolation) & 서가(책장) 아카이브 캐싱 (SQLite)
* **동시성 안전성 확보:** 다중 사용자 접속 시 전역 상태 오염(Race Condition)을 방지하기 위해 session_id 및 LangGraph MemorySaver(thread_id) 기반으로 파일 컨텍스트와 HITL 인터럽트 큐를 완벽히 격리했습니다.
* **비용  서가 캐시 히트 & 강제 재검색:** 동일·유사 질문 시 외부 API 호출 없이 SQLite 서가 DB에서 기존 검증 보고서를 즉시 인출(도트 오피스 내 책장 픽업 애니메이션 연동)하며, "다시 찾아줘" 입력 시 캐시를 우회해 최신 데이터를 재크롤링합니다.

### 5. 실시간 양방향 CEO 개입(Live Whisper) & 현업 2-Sheet 엑셀/워드 변환기
* **Live HITL 개입:** 에이전트 작업 도중 관리자가 실시간 추가 지침을 투입하면 실행 중인 워크플로우에 즉시 인터럽트로 반영됩니다.
* **현업 즉시 투입용 문서 변환:**
  * **Excel (.xlsx):** Sheet 1 (최종승인_결재보고서) + 자동 필터·숫자 타입 변환·부적합(NG) 행 빨간색 하이라이트가 적용된 Sheet 2 (전수검수_원본데이터) 동시 생성
  * **Word (.docx) / PDF / Markdown:** 표준 OpenXML 규격 워드 문서 및 인쇄용 PDF 즉시 발행
  * **ERP · Jira · Slack 웹훅 슬롯:** Ecount ERP 입고전표, Jira 이슈 티켓, Slack Block Kit 표준 JSON 페이로드 생성 및 전송 지원

---

## 🛠️ Tech Stack

| 영역 | 사용 기술 |
| :--- | :--- |
| **Frontend** | Next.js (App Router), TypeScript, Tailwind CSS, HTML5 Canvas (2.5D Pixel Office), Zustand, ReactFlow |
| **Backend** | Python 3.12, FastAPI, Asyncio, httpx.AsyncClient (100% Non-blocking I/O), Server-Sent Events (SSE) |
| **AI & Agent** | LangGraph (StateGraph, MemorySaver), Google Gemini API (2.5-flash / 2.0-flash), OpenAI API (gpt-4o-mini), Ollama |
| **Data & RPA** | Playwright (Async Chromium + Set-of-Mark), OpenPyXL, PyPDF, SQLite3 (mission_archive.db) |

---

## 🚀 Quick Start & Verification

`ash
# 1. 백엔드 서버 실행 (Port 8000)
venv\Scripts\uvicorn backend.main:app --reload --port 8000

# 2. 프론트엔드 개발 서버 실행 (Port 3000)
npm run dev

# 3. 엔터프라이즈 5대 기둥 & 현업 UAT 자동 검증 테스트 실행
venv\Scripts\python tests/test_enterprise_suite.py
venv\Scripts\python upgrade_field_ready.py

