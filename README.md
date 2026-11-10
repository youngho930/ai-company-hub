# 🏢 AI Company Hub — Enterprise Multi-Agent Mission Control (v3.5)

> **LangGraph 기반 자율형 멀티 에이전트 오케스트레이션 & 8대 국제 품질·규제 인증(ISO/IATF/RoHS) 심사 · 결정론적 CoA/PPM/CAPA 분석 및 2.5D 아케이드 관제 플랫폼**

단순 질의응답(Chatbot)의 한계를 넘어, 사내 5개 전문 부서(인사·리서치, AI·SW개발, 품질·생산QA, 재무·데이터, 마케팅·전략)의 AI 에이전트들이 역할을 분담해 **웹·문서 크롤링 ➔ 결정론적 통계·PPM·파레토 연산 ➔ 8대 국제규격 Gap 심사 ➔ 팀장급 정량 루브릭 검수(QC Gate) ➔ 반려 시 2차 심화 재조사 ➔ 다중 포맷(Word/Excel/PDF) 보고서 발행 및 ERP 연동**을 수행하는 엔터프라이즈 AI 워크플로우 시스템입니다.

---

## ✨ 핵심 엔지니어링 아키텍처 (6 Pillars)

### 1. 비조작(Un-rigged) 동적 QC 루브릭 & 자율 ReAct 재조사 루프 (LangGraph)
* **정량 루브릭 검수 게이트 (85점 기준):** 1차 수집 팩트 밀도(35점), 정량·통계 근거(35점), 교차검증 깊이(30점)를 정량 채점합니다.
* **조건부 분기 (`route_after_qc`):** 1차 조사에서 충분한 정량 데이터가 확보되면 재조사 없이 즉시 승인(**Fast-Track**)하고, 기준 미달 시 팀장이 반려(`QC_REJECT`)하여 부족한 키워드를 보완한 **2차 심화 쿼리로 실제 Playwright 재크롤링**을 수행합니다.

### 2. 결정론적(Deterministic) 전수 데이터 연산 & PPM · Pareto · 5-Why · CAPA 자동 분석
* LLM의 산술 환각(Hallucination)을 원천 차단하기 위해 Python(OpenPyXL / CSV) 기반 전수 데이터 연산기를 탑재했습니다.
* **스마트 헤더 탐지:** 현업 엑셀/CSV 상단(1~10행)의 결재란·문서번호 병합 행을 자동으로 건너뛰고 실제 데이터 헤더 행을 식별합니다.
* **수학적 공차(Tolerance) 자동 판정:** 성적서(CoA)에 합격/불합격 열이 없어도 `15.0 ± 0.5`, `120 이상`, `100 이하`, `95 ~ 105` 등의 기준 규격(Spec) 문자열을 정규식으로 해독해 실측치와의 편차 및 적격 여부를 오차 0%로 자동 연산합니다.
* **PPM · 파레토(Pareto) · CAPA 자동 도출:**
  * ① 총 불량률(%) 및 공정 불량 지수 **PPM(Parts Per Million)** 자동 계산
  * ② 불량 유형·항목별 **파레토(Pareto 80:20) 빈도 및 누적 비중(%)** 자동 층별화
  * ③ 기준치 초과 품목에 대한 **5-Why 근본원인 분석** 및 **CAPA(시정·예방조치) / 8D 대책** 자동 생성

### 3. 확장형 8대 국제 품질·규제 인증 레지스트리 (`COMPLIANCE_STANDARDS_REGISTRY`) & 동적 폴백 심사 엔진
업로드된 작업표준서(SOP)·품질매뉴얼·성적서 또는 사용자 프롬프트에서 단일/복합 국제 규격을 자동 감지하여 조항별 **[적합(Compliant) / 보완필요(Gap)]** 정량 판정과 인증 심사 통과용 시정 가이드를 도출합니다.
* **`ISO 9001`:** 품질경영시스템 (리스크 기반 사고 6.1, 문서화된 정보 7.5, 고객만족 및 부적합 통제 8.7/10.2)
* **`ISO 13485`:** 의료기기 품질경영시스템 (4.2.3 의료기기 파일 MDF, 4.2.4 문서·기록 보존기한, 7.5.6 특수공정 밸리데이션 IQ/OQ/PQ, 7.5.8 LOT 추적성, 8.5.2 CAPA)
* **`ISO 14971`:** 의료기기 위험관리 (위해요인 식별, 심각도×발생빈도 위험산정 RPN, 3단계 위험통제, 잔여위험 평가 및 FMEA 연계)
* **`IEC 60601 / IEC 62304`:** 전자의료기기 전기·기계적 안전성(누설전류·2중 절연·EMC) 및 의료기기 SW 수명주기 안전 등급(Class A/B/C)
* **`KGMP / FDA 21 CFR Part 820`:** 식약처 의료기기 GMP 및 미국 FDA QMSR (제품표준서 DMR, 제조이력서 DHR, 이상사례 MDR 보고 및 강제/자진 회수 Recall)
* **`IATF 16949`:** 자동차·전장 품질경영 5 Core Tools (`APQP`, `PPAP 18종 PSW`, `AIAG-VDA FMEA`, `MSA 게이지 %GRR`, `SPC 관리도 및 Ppk ≥ 1.67 / Cpk ≥ 1.33`)
* **`ISO 14001 / ISO 45001`:** 환경·안전보건경영 (전과정 LCA 환경측면 영향평가, 근로자 참여형 위험성평가, 아차사고 Near-Miss, 비상사태 대응 및 법규준수)
* **`RoHS / REACH`:** 유해물질 제한 및 CoA/MSDS 관리 (`Cd ≤ 100ppm`, `Pb·Hg·Cr6+·PBB·PBDE·프탈레이트 ≤ 1,000ppm`, REACH SVHC 0.1 wt% 보증)
* **미등록 규격 실시간 크롤링 폴백(Fallback):** 레지스트리에 없는 기타 인증(예: `ISO 27001`, `HACCP`, `ISMS-P`, `CE MDR` 등) 입력 시 `vision_browser.py` 다중 지식 수집기와 실시간 연동해 해당 규격의 핵심 요건을 크롤링하여 동적 Gap 분석 보고서를 생성합니다.

### 4. 4중 하이브리드 지식 수집 & Set-of-Mark (SoM) Vision 브라우징
* **다중 출처 교차 수집:** 개인 블로그 노이즈를 배제하고 ① Wikipedia 공식 REST/Action API, ② 네이버 지식백과, ③ Google News 실시간 RSS, ④ Playwright 헤드리스 브라우저를 결합해 할루시네이션 없는 팩트를 수집합니다.
* **SoM 시각적 그라운딩:** 웹 페이지 내 상호작용 요소에 빨간색 번호표(Bounding Box)를 부여하고 실시간 스캔 프레임을 스트리밍합니다.

### 5. 세션 동시성 격리(Session Isolation) & 서가(책장) 아카이브 캐싱 (SQLite)
* **동시성 안전성 확보:** 다중 사용자 접속 시 전역 상태 오염(Race Condition)을 방지하기 위해 `session_id` 및 LangGraph `MemorySaver(thread_id)` 기반으로 파일 컨텍스트와 HITL 인터럽트 큐를 완벽히 격리했습니다.
* **비용 $0 서가 캐시 히트 & 강제 재검색:** 동일·유사 질문 시 외부 API 호출 없이 SQLite 서가 DB에서 기존 검증 보고서를 즉시 인출하며, `"다시 찾아줘"` 입력 시 캐시를 우회해 최신 데이터를 재크롤링합니다.

### 6. 고해상도 2.5D 아케이드 오피스 & 실시간 양방향 CEO 개입(Live Whisper)
* **2.5D 아케이드 사옥 & SD 캐릭터:** 메탈 몰딩 프레임, 부서별 특화 오브젝트(QA 컨베이어 벨트·안전모, 개발팀 홀로그램 큐브·로봇, 중앙 회의실 골드 월계관·6인승 원형 테이블 등), `createRadialGradient` 네온 블룸 조명, 감속 보간 및 Squash & Stretch 탄성 모션, 이동 잔상 트레일(Path Trail)을 구현했습니다.
* **현업 즉시 투입용 문서 변환 & 웹훅 연동:**
  * **Excel (`.xlsx`):** `Sheet 1 (최종승인_결재보고서)` + 자동 필터·숫자 타입 변환·부적합(NG) 행 하이라이트가 적용된 `Sheet 2 (전수검수_원본데이터)` 동시 생성
  * **Word (`.docx`) / PDF / Markdown** 및 **Ecount ERP · Jira · Slack 웹훅** 표준 페이로드 연동

---

## 📂 포트폴리오 시연용 현업 샘플 파일 (`samples/`)

상단 헤더의 **`📎 파일 첨부`** 버튼을 클릭해 아래 샘플 파일을 업로드하면 즉시 실무 품질 심사 및 자동 규격 판정을 시연할 수 있습니다:
1. **`samples/의료기기_멸균포장_SOP_초안.txt`**
   * 문서번호·개정이력·LOT 추적성은 포함되어 있으나, **특수공정 밸리데이션(IQ/OQ/PQ), ISO 14971 위험관리(RPN 산정·잔여위험 평가), CAPA 유효성 검증 절차**가 의도적으로 누락되어 AI가 조항별 Gap과 보완 가이드를 정량 검출하는 테스트용 작업표준서(SOP) 초안입니다.
2. **`samples/전장부품_수입검사_RoHS_성적서.csv`**
   * 상단 1~2행 결재란을 자동 스킵하고 본문 8개 LOT의 **도금두께·내경치수 공차(`15.0±0.5`), RoHS 중금속(`Cd 100ppm 이하`, `Cr6+ 1000ppm 이하`), 인장강도(`120 이상`)**를 수학적으로 자동 판정하여 **불량률(37.5%, 375,000 PPM), 파레토(Pareto) 분석, 5-Why 및 IATF 16949 SPC/CAPA 대책**을 동시에 도출하는 실무 성적서 데이터입니다.

---

## 🛠️ Tech Stack

| 영역 | 사용 기술 |
| :--- | :--- |
| **Frontend** | Next.js (App Router), TypeScript, Tailwind CSS, HTML5 Canvas (2.5D Arcade Office), Zustand, ReactFlow |
| **Backend** | Python 3.12, FastAPI, Asyncio, `httpx.AsyncClient` (100% Non-blocking I/O), Server-Sent Events (SSE) |
| **AI & Agent** | LangGraph (`StateGraph`, `MemorySaver`), Google Gemini API, OpenAI API (`gpt-4o-mini`), Multi-Standard Compliance Registry |
| **Data & RPA** | Playwright (Async Chromium + Set-of-Mark), OpenPyXL, PyPDF, SQLite3 (`mission_archive.db`) |

---

## 🚀 Quick Start & Verification

```bash
# 1. 백엔드 서버 실행 (Port 8000)
venv\Scripts\uvicorn backend.main:app --reload --port 8000

# 2. 프론트엔드 개발 서버 실행 (Port 3000)
npm run dev

# 3. 엔터프라이즈 6대 기둥 & 다중 국제규격 레지스트리 자동 검증 테스트 실행
venv\Scripts\python tests/test_enterprise_suite.py
```
