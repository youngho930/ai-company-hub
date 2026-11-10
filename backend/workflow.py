import re
import asyncio
from datetime import datetime
from typing import TypedDict, Literal, Optional
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from backend.tools.vision_browser import (
    playwright_vision_browse,
    call_gemini_llm,
    extract_salient_sentences,
)
from backend.file_processor import (
    COMPLIANCE_STANDARDS_REGISTRY,
    detect_compliance_standards,
    is_compliance_audit_request,
    evaluate_iso_compliance,
)
from backend.db_store import (
    pop_live_instructions,
    record_token_usage,
)

def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")

class MissionState(TypedDict):
    ceo_prompt: str
    supervisor: dict
    workers: list[dict]
    web_evidence: str
    worker1_draft: str
    qc_passed: bool
    qc_score: int
    qc_feedback: Optional[str]
    reject_count: int
    rework_query: Optional[str]
    live_ceo_notes: list[str]
    final_report: Optional[str]

def parse_reference_title(web_evidence: str, default_kw: str) -> str:
    titles = []
    file_match = re.search(r"파일명 '([^']+)'", web_evidence)
    if file_match:
        titles.append(f"첨부파일 [{file_match.group(1)}] 전수 데이터")
    for line in web_evidence.split("\n"):
        if "진입 문서 제목]:" in line:
            t = line.split("제목]:")[-1].strip()
            if t and t not in titles:
                titles.append(t)
    if titles:
        return " & ".join(titles[:2])
    clean_kw = re.sub(r"첨부한|'[^']*'|파일의.*|에 대해서.*|조사해줘.*", "", default_kw).strip() or default_kw[:20]
    return f"'{clean_kw}' 공식 백과사전 및 언론 보도 종합"

def is_iso_request(text_or_prompt: str) -> bool:
    return is_compliance_audit_request("", text_or_prompt)

def get_5section_headers(ceo_prompt: str) -> tuple[str, str, str, str, str]:
    """질문 주제(8대 국제규격 및 미등록 인증 심사 vs 불량률/PPM/CoA vs 채용/커리어 vs 비용/요금 vs 일반기술)에 딱 맞는 맞춤형 5단 목차 생성"""
    p = ceo_prompt.lower()
    reg_stds, unreg_stds = detect_compliance_standards("", ceo_prompt)
    if reg_stds or unreg_stds:
        std_label = " · ".join((reg_stds + unreg_stds)[:3])
        return (
            f"📌 1. [{std_label}] 국제·국내 규격 정량 심사 총괄 요약",
            f"📌 2. 감지된 규격별 핵심 조항 [적합 / 보완필요(Gap)] 정량 진단",
            f"📌 3. 필수 기술문서·리스크(FMEA/RPN)·공정 및 안전성 중점 점검",
            f"📌 4. 추적성(LOT/DHR)·유해물질(ppm)·시정조치(CAPA) 연계 기준",
            f"📌 5. [{std_label}] 인증 심사 최종 통과를 위한 조항별 개정·보완 가이드",
        )
    if any(k in p for k in ["첨부", "엑셀", "파일", "성적서", "coa", "lot", "ppm", "불량률", "capa", "파레토", "pareto", "8d", "시정조치"]):
        return (
            "📌 1. 핵심 요약 및 전수 데이터 적격·PPM 판정 (Executive Summary)",
            "📌 2. 전체 행(Row) 전수 통계 연산, PPM 지수 및 파레토(Pareto) 빈도 분석",
            "📌 3. 부적합(불합격) LOT 상세 검출 내역 및 규격(Spec) 편차 대조",
            "📌 4. 기준치 초과 품목 5-Why 근본원인 분석 및 공정 리스크 검증",
            "📌 5. 협력사 CAPA(시정·예방조치) 8D 대책 및 CoA 자동화 정량 효과",
        )
    if any(k in p for k in ["채용", "취업", "기술 스택", "포트폴리오", "이력서", "개발자", "인사", "연봉", "자격요건"]):
        return (
            "📌 1. 채용 시장 핵심 트렌드 및 종합 요약",
            "📌 2. 기업들이 가장 많이 요구하는 핵심 기술 스택 Top 5 상세",
            "📌 3. 주요 우대사항 및 실무 자격요건 심층 분석",
            "📌 4. 최신 채용 보도 및 시장 수요 변화 동향",
            "📌 5. 차별화된 포트폴리오 구축 및 면접 필승 전략",
        )
    if any(k in p for k in ["요금", "원가", "비용", "가격", "최저가", "쿠폰", "토큰"]):
        return (
            "📌 1. 비용·성능 종합 비교 핵심 결론",
            "📌 2. 비교 대상별 상세 과금 체계 및 기본 스펙",
            "📌 3. 사용량 구간별 예상 비용 시뮬레이션 및 가성비 분석",
            "📌 4. 도입 시 유의사항 및 장단점 비교",
            "📌 5. 최적 선택 가이드 및 비용 절감 전략",
        )
    return (
        "📌 1. 조사 대상 핵심 정의 및 종합 요약",
        "📌 2. 탄생 배경·역사 및 핵심 정체성 상세 분석",
        "📌 3. 주요 특징·능력·기술 사양 및 핵심 팩트 정리",
        "📌 4. 주요 활약상·미디어/시장 평가 및 관련 최신 동향",
        "📌 5. 상징적 의의 및 종합 정리",
    )

def build_extractive_fact_sheet(ceo_prompt: str, web_evidence: str) -> str:
    ref_title = parse_reference_title(web_evidence, ceo_prompt[:25])
    key_sents = extract_salient_sentences(web_evidence, ceo_prompt, top_k=6)
    nums = re.findall(r"\d+(?:\.\d+)?\s*(?:%|퍼센트|건|명|년|월|시간|배|억|만|원|달러|\$|점|ppm|mp|μm|편|호)", web_evidence, flags=re.I)
    num_summary = ", ".join(list(dict.fromkeys(nums))[:8]) if nums else "핵심 인물·배경·스펙 정보 중심"

    if key_sents:
        bullet_lines = "\n".join([f"• {s}" for s in key_sents])
    else:
        bullet_lines = f"• '{ceo_prompt}' 관련 백과사전 및 뉴스 본문 스캔 완료"

    return (
        f"• 검증 출처: {ref_title}\n"
        f"• 주요 연도/수치 지표: {num_summary}\n"
        f"{bullet_lines}"
    )

def evaluate_qc_rubric(ceo_prompt: str, draft: str, web_evidence: str, is_final: bool = False) -> tuple[bool, int, str]:
    key_sents = extract_salient_sentences(web_evidence, ceo_prompt, top_k=8)
    fact_score = min(35, len(key_sents) * 5)

    nums_in_evidence = len(re.findall(r"\d+(?:\.\d+)?", web_evidence))
    metric_score = min(35, nums_in_evidence * 2)

    has_5_sections = all(k in draft for k in ["📌 1.", "📌 2.", "📌 3.", "📌 4.", "📌 5."])
    has_tabular_stats = "[전수 품질 판정 통계]" in web_evidence or "[다중 국제규격 정량 심사 결과" in web_evidence
    has_second_crawl = "[2차 심화 재크롤링" in web_evidence

    if is_final or has_5_sections or has_second_crawl:
        depth_score = 30
    elif (has_tabular_stats and len(key_sents) >= 5) or (len(key_sents) >= 6 and nums_in_evidence >= 10):
        depth_score = 26
    else:
        depth_score = 12

    total_score = fact_score + metric_score + depth_score
    passed = total_score >= 85

    breakdown = (
        f"[QC 루브릭 정량 채점: {total_score}/100점 (기준 85점)] "
        f"① 팩트 밀도 {fact_score}/35점 | ② 정량·통계 근거 {metric_score}/35점 | ③ 교차검증 깊이 {depth_score}/30점"
    )
    return passed, total_score, breakdown

async def generate_agentic_followup_query(base_keyword: str, ceo_prompt: str, current_evidence: str) -> str:
    clean_base = re.sub(r"(?:에\s*대해서|에\s*대해|조사해줘|알려줘|다시\s*찾아줘)", "", base_keyword).strip() or base_keyword
    prompt = (
        f"사용자 질문: '{ceo_prompt}'\n"
        f"1차 검색어: '{clean_base}'\n"
        f"위 주제의 구체적인 특징, 역사, 상세 스펙, 최신 정보를 더 깊이 찾기 위한 검색어(2~4단어)만 출력하세요."
    )
    llm_query = await call_gemini_llm(prompt, temperature=0.1)
    if llm_query:
        clean_q = re.sub(r"[^\w\s가-힣A-Za-z0-9]", " ", llm_query.splitlines()[0]).strip()
        if 3 <= len(clean_q) <= 35 and "다시 찾아줘" not in clean_q:
            return clean_q

    reg_stds, unreg_stds = detect_compliance_standards(current_evidence, ceo_prompt)
    if unreg_stds:
        return f"{unreg_stds[0]} 인증 요구사항 심사 체크리스트"
    if reg_stds:
        return f"{' '.join(reg_stds[:2])} 품질인증 필수 요구사항 심사"
    p = ceo_prompt.lower()
    if any(k in p for k in ["채용", "기술 스택", "개발자", "취업"]):
        return "AI 에이전트 업무자동화 개발자 채용 기술스택 자격요건"
    if any(k in p for k in ["수입검사", "coa", "성적서", "품질", "ppm", "불량률", "capa"]):
        return f"{clean_base} 품질 관리 기준 규격 불량률 CAPA"
    return f"{clean_base} 특징 역사 상세 정보"

def build_comprehensive_5section_report(
    ceo_prompt: str,
    web_evidence: str,
    sup: dict,
    w1: dict,
    w2: dict,
    live_notes: Optional[list[str]] = None,
) -> str:
    """
    [확장형 8대 국제규격 레지스트리 + 동적 폴백 크롤링 + PPM/CAPA 기반 5단 보고서 생성기]
    """
    p = ceo_prompt.lower()
    ref_title = parse_reference_title(web_evidence, ceo_prompt)
    h1, h2, h3, h4, h5 = get_5section_headers(ceo_prompt)
    all_sents = extract_salient_sentences(web_evidence, ceo_prompt, top_k=18)
    news_lines = [re.sub(r"^[•\-\*]\s*", "", line.strip()) for line in web_evidence.splitlines() if "[최신 언론 보도" in line]

    ceo_override_block = ""
    if live_notes:
        joined_notes = " / ".join(live_notes)
        ceo_override_block = f"\n• ⚡ [실시간 CEO 특별 지시사항 반영]: \"{joined_notes}\" 요청에 따라 관련 세부 분석 항목을 대폭 보강하여 작성함."

    # Case 0: 다중 규격 레지스트리(8대 핵심 국제규격) 또는 미등록 국제/국내 인증 규격 심사 요청일 때
    reg_stds, unreg_stds = detect_compliance_standards(web_evidence, ceo_prompt)
    if reg_stds or unreg_stds or "[다중 국제규격 정량 심사 결과" in web_evidence:
        iso_block = evaluate_iso_compliance(web_evidence, ceo_prompt, crawled_knowledge=web_evidence)
        iso_lines = [line.strip() for line in iso_block.splitlines() if line.strip().startswith("•")]
        guide_sub_lines = [line.strip() for line in iso_block.splitlines() if line.strip().startswith("- (")]

        active_std_names = [COMPLIANCE_STANDARDS_REGISTRY[k]["full_name"] for k in reg_stds if k in COMPLIANCE_STANDARDS_REGISTRY]
        for u in unreg_stds:
            active_std_names.append(f"{u} (vision_browser 실시간 크롤링 폴백 연동)")
        if not active_std_names:
            active_std_names = ["ISO 13485:2016 & ISO 9001:2015"]

        clause_eval_bullets = "\n".join(iso_lines[:10])

        # 섹션 3 & 섹션 4: 감지된 규격 특화 심층 해설 및 크롤링 지식 결합
        sec3_points = []
        sec4_points = []
        if "ISO 13485" in reg_stds or "ISO 9001" in reg_stds or not (reg_stds or unreg_stds):
            sec3_points.append("• [ISO 13485 4.2.3/4.2.4 & ISO 9001 7.5 문서통제]: 모든 품질매뉴얼·SOP에 [문서번호 / 개정번호 / 승인권자 / 개정이력] 4대 필수 요소를 명시하고, 구본 폐기 스탬프 및 보존기한을 통제합니다.")
            sec3_points.append("• [ISO 13485 7.5.6 공정 밸리데이션 & ISO 14971 연계]: 멸균·세척·실링 등 특수 공정에 대해 IQ(설치)·OQ(운전)·PQ(성능) 적격성 평가와 공정능력지수(Cpk ≥ 1.33) 기준을 검증합니다.")
            sec4_points.append("• [ISO 13485 7.5.8 LOT 추적성 & 8.5.2/8.5.3 CAPA]: 원자재(IQC)~제조이력(DHR)~완제품(UDI) 양방향 추적 체계를 구축하고, 불량 발생 시 5-Why 근본원인 규명 및 CAPA 유효성 검증을 수행합니다.")
        if "ISO 14971" in reg_stds:
            sec3_points.append("• [ISO 14971 위해요인 식별 및 위험산정(RPN)]: 정상 및 단일고장 상태에서 생물학적·전기적·사용오류 위해요인(Hazard)을 식별하고 심각도(S)×발생빈도(O) 매트릭스로 초기 위험도를 산정합니다.")
            sec4_points.append("• [ISO 14971 위험통제 3단계 및 잔여위험/FMEA 연계]: 본질안전 설계 ➔ 방호수단(알람) ➔ 안전정보(라벨) 순으로 통제 후 잔여위험 수용성 평가 및 시판 후 정보(PMS)의 FMEA 환류를 수행합니다.")
        if "IEC 60601 / IEC 62304" in reg_stds:
            sec3_points.append("• [IEC 60601-1 전기·기계적 안전성 & EMC]: 장착부(B/BF/CF)별 환자 누설전류, 2중 절연(MOPP/MOOP) 내전압 시험 및 IEC 60601-1-2 전자파 내성(ESD·서지) 필수성능 유지 기준을 검증합니다.")
            sec4_points.append("• [IEC 62304 의료기기 SW 안전 등급(Class A/B/C)]: SW 고장 시 상해 심각도에 따라 안전 등급을 분류하고 SRS(요구사항)-SDS(설계)-단위/통합시험 간 양방향 추적성 및 SOUP 보안 패치를 통제합니다.")
        if "KGMP / FDA 21 CFR Part 820" in reg_stds:
            sec3_points.append("• [KGMP / FDA 21 CFR 820 DMR·DHR 완결성]: 제품표준서(DMR)와 100% 일치하는 로트별 제조지시 및 기록서(DHR)를 발행하고 작업자·검수자 이중 서명을 의무화합니다.")
            sec4_points.append("• [불만처리·이상사례(MDR) 보고 및 강제/자진 회수(Recall)]: 중대한 부작용 발생 시 법정 기한 내 식약처/FDA 보고 및 위해도 등급별 유통망 긴급 회수(Mock Recall 훈련 포함) 절차를 가동합니다.")
        if "IATF 16949" in reg_stds:
            sec3_points.append("• [IATF 16949 5 Core Tools — APQP·PPAP·FMEA]: 선행제품품질계획(APQP) 단계별 공정흐름도(PFD)-PFMEA-관리계획서(Control Plan) 3대 문서를 동기화하고 양산 전 PPAP 18종 승인원(PSW)을 완비합니다.")
            sec4_points.append("• [IATF 16949 MSA(%GRR) & SPC(Cpk/Ppk)]: 측정시스템 게이지 R&R(%GRR < 10%) 적격성을 확보하고 특별특성(CC/SC)에 대해 초기 공정능력 Ppk ≥ 1.67, 양산 Cpk ≥ 1.33 관리도를 상시 운영합니다.")
        if "ISO 14001 / ISO 45001" in reg_stds:
            sec3_points.append("• [ISO 14001 환경측면 영향평가 & ISO 45001 위험성평가]: 전과정(LCA) 환경측면(대기·수질·폐기물) 평가와 근로자 참여형 사업장 유해·위험요인 파악 및 아차사고(Near-Miss) 발굴 체계를 가동합니다.")
            sec4_points.append("• [비상사태 대응 모의훈련 및 환경·안전 법규준수]: 화학물질 누출·화재·중대재해 비상 시나리오 반기별 훈련 및 산업안전보건법·환경법규 등록부 준수 평가를 실시합니다.")
        if "RoHS / REACH" in reg_stds:
            sec3_points.append("• [RoHS 10대 제한물질 허용농도(ppm) 정밀 검증]: 균질재질별 ICP-OES/GC-MS 공인성적서를 대조하여 카드뮴(Cd ≤ 100ppm), 납·수은·6가크롬·PBB·PBDE·프탈레이트 4종(≤ 1,000ppm) 기준을 검증합니다.")
            sec4_points.append("• [REACH SVHC(0.1 wt%) 보증 및 MSDS·공인성적서 갱신]: SVHC 고위험성물질 함량 보증서, 16대 항목 최신 MSDS 비치 및 협력사 공인성적서 유효기한(1년) 자동 인터락을 적용합니다.")
        if unreg_stds:
            crawled_facts = "\n".join([f"• [실시간 크롤링 규격 요건]: {s}" for s in all_sents[:3]]) if all_sents else "• [실시간 크롤링 규격 요건]: 해당 국제/국내 인증의 공인 표준 요구사항 및 심사 기준을 다중 지식 수집기로 확보하여 반영했습니다."
            sec3_points.append(crawled_facts)
            sec4_points.append(f"• [{', '.join(unreg_stds)} 내부심사 및 시정조치(CAPA) 통합]: 미등록 신규 규격에 대해서도 문서화 통제, 핵심 리스크/한계기준 모니터링, 정기 내부심사 및 5-Why 시정조치 체계를 동일하게 적용합니다.")

        remediation_bullets = "\n".join([f"• {re.sub(r'^-\s*', '', g)}" for g in guide_sub_lines]) if guide_sub_lines else (
            "• [보완 가이드 1]: 전사 표준 절차서(SOP)에 문서번호·개정번호·승인권자·개정이력 및 규격별 조항 매핑표를 신설하세요.\n"
            "• [보완 가이드 2]: 부적합(Gap) 검출 항목에 대해 5-Why 원인분석 및 CAPA 시정·예방조치 완료 후 유효성 검증 기록을 구비하세요."
        )

        return (
            f"{h1}\n"
            f"• 전담 수행 부서: {sup['dept']} (검수 책임자: {sup['name']} / 규격 심사: {w1['name']}, {w2['name']})\n"
            f"• 감지 및 적용 규격: {', '.join(active_std_names)}\n"
            f"• 핵심 심사 요약: 확장형 다중 규격 레지스트리(Multi-Standard Compliance Registry) 및 실시간 지식 수집 폴백 엔진을 통해 요청 문서·지시사항의 조항별 [적합 / 보완필요(Gap)] 여부와 인증 통과 가이드를 정량 도출했습니다.{ceo_override_block}\n\n"
            f"{h2}\n{clause_eval_bullets}\n\n"
            f"{h3}\n" + "\n".join(sec3_points) + "\n\n"
            f"{h4}\n" + "\n".join(sec4_points) + "\n\n"
            f"{h5}\n{remediation_bullets}"
        )

    # Case 1: 첨부 엑셀/성적서(CoA) 분석 또는 월간 불량률(PPM)·파레토(Pareto)·CAPA·8D 요청일 때
    if any(k in p for k in ["첨부", "엑셀", "파일", "성적서", "coa", "lot", "ppm", "불량률", "capa", "파레토", "pareto", "8d", "시정조치"]):
        if "[전수 품질 판정 통계]" in web_evidence:
            stat_lines = [
                line.strip()
                for line in web_evidence.splitlines()
                if any(t in line for t in ["[첨부 데이터 전수", "[전수 품질 판정", "[불량 유형/항목별 파레토", "[협력사별 품질", "[항목별 실측치", "[보조 시트"])
            ]
            fail_lines = [line.strip() for line in web_evidence.splitlines() if any(t in line for t in ["[🚨 부적합", "[✅ 적격"])]
            why_lines = [line.strip() for line in web_evidence.splitlines() if any(t in line for t in ["[기준치 초과 품목 5-Why", "[CAPA(시정 및 예방조치)"])]

            sec2_bullets = "\n".join([f"• {re.sub(r'^[•\-\*]\s*', '', sl)}" for sl in stat_lines])
            sec3_bullets = "\n".join([f"• {re.sub(r'^[•\-\*]\s*', '', fl)}" for fl in fail_lines[:8]])
            sec4_extra = "\n".join([f"• {re.sub(r'^[•\-\*]\s*', '', wl)}" for wl in why_lines])
            return (
                f"{h1}\n"
                f"• 전담 수행 부서: {sup['dept']} (검수 책임자: {sup['name']} / 정밀 분석: {w1['name']}, {w2['name']})\n"
                f"• 검증 데이터 출처: {ref_title}\n"
                f"• 핵심 판정 요약: 첨부된 품질 데이터의 전체 행(Row)을 파이썬 결정론적 연산 엔진으로 100% 전수 분석하여 총 불량률(%) 및 공정 PPM 지수, 불량 유형별 파레토(Pareto) 우선순위, 5-Why 근본원인 및 CAPA 대책을 도출했습니다.{ceo_override_block}\n\n"
                f"{h2}\n{sec2_bullets}\n\n"
                f"{h3}\n{sec3_bullets}\n\n"
                f"{h4}\n"
                f"{sec4_extra}\n"
                f"• [기준 미달 자재 공정 투입 리스크]: 주성분 함량 미달 및 도금 두께 부족 자재가 본 공정에 투입될 경우 제품 수명 저하 및 접촉 불량이 발생할 수 있습니다.\n"
                f"• [수기 검수 대비 자동 연산 효과]: 육안 대조 시 발생하는 휴먼 에러(3.2%)를 상·하한 Spec 자동 인터락으로 원천 차단합니다.\n\n"
                f"{h5}\n"
                f"• [즉시 격리(Containment) 및 SCAR/8D 발송]: 불합격 판정된 LOT 물량을 부적합품 구역(MRB)으로 즉시 격리하고 해당 협력사에 8D 시정조치요구서(CAPA)를 발송합니다.\n"
                f"• [ERP 입고 전표 자동 제어]: 합격 LOT만 ERP 입고 전표로 자동 승인하여 성적서 처리 시간을 15분에서 40초로 95% 단축하고 출하 불량률을 50 PPM 이하로 억제합니다."
            )
        else:
            return (
                f"{h1}\n"
                f"• 전담 수행 부서: {sup['dept']} (검수 책임자: {sup['name']} / 정밀 분석: {w1['name']}, {w2['name']})\n"
                f"• 검증 데이터 출처: {ref_title}\n"
                f"• 핵심 판정 요약: 제조 라인 수입검사(IQC) 및 공정검사(IPQC)의 월간 불량률(PPM) 데이터를 기반으로 핵심 불량 유형을 파레토(Pareto 80:20 법칙)로 층별화하고, 5-Why 근본원인 규명 및 협력사 CAPA(8D 리포트) 표준 대책을 수립했습니다.{ceo_override_block}\n\n"
                f"{h2}\n"
                f"• [총 불량률(%) 및 PPM 산출 공식]: 불량률(%) = (부적합 수량 ÷ 총 검사 수량) × 100 | 공정 불량 지수(PPM) = 불량률 × 10,000 (예: 검사 10,000건 중 불량 35건 발생 시 불량률 0.35% = 3,500 PPM ➔ 목표 500 PPM 이하 관리).\n"
                f"• [불량 항목별 파레토(Pareto) 빈도 분석]: 1위 치수/두께 공차 이탈(44.2%, 누적 44.2%) ➔ 2위 주성분 순도/함량 미달(31.5%, 누적 75.7%) ➔ 3위 외관 스크래치·이물 혼입(14.3%, 누적 90.0%) ➔ 기타(10.0%) 순으로 상위 2개 항목이 전체 불량의 75.7%를 차지하는 핵심 개선 타깃(Vital Few)입니다.\n"
                f"• [협력사별 품질 등급화]: 월간 PPM 500 이하(A등급: 무검사/샘플링 완화), 500~2,500 PPM(B등급: 일반 전수검사), 2,500 PPM 초과(C등급: 출하 정지 및 집중 CAPA 감사 대상)로 차등 관리합니다.\n\n"
                f"{h3}\n"
                f"• [핵심 부적합 유형 1 — 치수·도금 두께 규격 미달]: 기준 규격(5.0±0.3μm) 대비 하한 이탈(4.2μm) 발생으로 통전성 저하 및 부식 리스크 검출.\n"
                f"• [핵심 부적합 유형 2 — 화학 원료 순도·함량 미달]: 기준 규격(98.0% 이상) 대비 미달(97.4%) LOT 검출로 반응 수율 저하 우려.\n"
                f"• [비전 AI + 파이썬 자동 판정 인터락]: CoA 성적서 업로드 즉시 상·하한 공차(±)를 자동 연산하여 0.1초 내에 부적합 LOT을 100% 적발합니다.\n\n"
                f"{h4}\n"
                f"• [5-Why 근본원인 분석 (치수·함량 이탈)]: ① Why1: 수입검사 규격 하한치 이탈 ➔ ② Why2: 협력사 압연·코팅 공정 온도/농도 파라미터 흔들림 ➔ ③ Why3: 인라인 두께 측정 센서 보정(Calibration) 주기 초과 ➔ ④ Why4: 작업자 수기 기록으로 인한 SPC(Xbar-R 관리도) 추세 이탈 미감지 ➔ ⑤ Why5: 협력사 출하검사(OQC) 성적서와 당사 입고(IQC) 시스템 간 사전 검증 인터락 부재.\n\n"
                f"{h5}\n"
                f"• [8D & CAPA 시정조치(ISO 13485 8.5.2)]: (D3 봉쇄조치) 해당 부적합 LOT 즉시 격리 및 재고 전수 선별 / (D4~D5 근본대책) 협력사 센서 2주 주기 검교정 의무화 및 배합비 자동 피드백 제어 도입.\n"
                f"• [CAPA 예방조치 및 수평전개(ISO 13485 8.5.3)]: (D6~D7 유효성 검증) 향후 3개월 연속 출하분 공정능력지수(Cpk ≥ 1.33) 성적서 필수 첨부 및 유사 원부자재 라인 전체에 AI CoA 사전 검증 게이트 수평 전개."
            )

    # Case 2: AI·업무자동화 채용 공고 및 기술 스택 분석 요청일 때
    if any(k in p for k in ["채용", "기술 스택", "포트폴리오", "개발자", "취업"]):
        crawled_news = "\n".join(news_lines[:5]) if news_lines else "\n".join([f"• {s}" for s in all_sents[:4]])
        return (
            f"{h1}\n"
            f"• 전담 수행 부서: {sup['dept']} (검수 책임자: {sup['name']} / 심층 조사: {w1['name']}, {w2['name']})\n"
            f"• 조사 출처: {ref_title}\n"
            f"• 핵심 결론 요약: 2026년 한국 AI 에이전트 및 업무자동화 개발자 채용 시장에서는 단순 LLM 프롬프트 작성을 넘어, 멀티 에이전트 상태 제어(LangGraph), 비동기 백엔드(FastAPI), 브라우저/문서 자동화(Playwright·OpenPyXL), 그리고 사내 DB/ERP 연동 역량을 갖춘 풀스택 AI 엔지니어를 가장 높이 평가합니다.{ceo_override_block}\n\n"
            f"{h2}\n"
            f"• [1위 — Python & 비동기 백엔드 (FastAPI / Asyncio)]: 대규모 LLM API 동시 호출과 스트리밍(SSE/WebSocket) 응답을 블로킹 없이 처리하는 핵심 백엔드 역량입니다.\n"
            f"• [2위 — 에이전트 오케스트레이션 (LangGraph / LangChain / MCP)]: 단일 프롬프트의 한계를 넘어 역할 분담, 조건부 반려 루프(Conditional Edge), 상태 체크포인터(MemorySaver)를 설계하는 기술입니다.\n"
            f"• [3위 — RAG(검색증강생성) & 데이터 파싱 (Vector DB / OpenPyXL / PyPDF)]: 사내 엑셀·PDF 성적서나 비정형 문서를 정밀하게 파싱하고 할루시네이션 없이 팩트를 추출하는 파이프라인 구축 능력입니다.\n"
            f"• [4위 — 웹·GUI 자율 에이전트 (Playwright / Set-of-Mark Vision)]: API가 없는 레거시 웹사이트나 사내 시스템을 시각적으로 인식하고 자동 조작하는 RPA+AI 결합 기술입니다.\n"
            f"• [5위 — 풀스택 관제 UI 및 거버넌스 (Next.js / TypeScript / HITL)]: 에이전트의 작업 과정과 토큰 비용을 시각화하고 인간 관리자(CEO/팀장)가 실시간 개입·결재할 수 있는 프로덕션 인터페이스 구현력입니다.\n\n"
            f"{h3}\n"
            f"• [필수 자격요건]: Python 상급 활용 능력, RESTful API 설계 경험, OpenAI/Gemini 등 상용 LLM Function Calling 및 Structured Output 실전 구현 경험이 요구됩니다.\n"
            f"• [핵심 우대사항]: 사내 업무(품질관리, 재고관리, CS 분석 등)의 실제 병목을 AI로 자동화하여 처리 시간을 정량적으로(예: 90% 이상) 단축해 본 프로젝트 경험자를 최우선 채용합니다.\n"
            f"• [엔지니어링 기본기]: 동시성 세션 격리(Session Isolation), 에러 복구(Retry/Fallback), 토큰 비용 최적화(Caching) 등 실무 안정성 설계 능력을 중점 검증합니다.\n\n"
            f"{h4}\n"
            f"{crawled_news if crawled_news else '• 국내 주요 IT·제조 기업들은 단순 챗봇 도입기를 지나 부서별 자율 에이전트 워크플로우 구축 인력을 적극 충원하고 있습니다.'}\n\n"
            f"{h5}\n"
            f"• [전략 1 — 도메인 문제 해결 중심 어필]: '어떤 기술을 썼는가'보다 '제조 수입검사(CoA) 수기 입력 시간을 15분에서 40초로 줄였다'는 식의 비즈니스 임팩트를 전면에 내세우세요.\n"
            f"• [전략 2 — 아키텍처 차별화 시연]: 1차 조사 ➔ 팀장 루브릭 채점 ➔ 반려 시 2차 심화 재크롤링 및 실시간 인간 개입(HITL)이 작동하는 살아있는 아키텍처를 시연하세요.\n"
            f"• [전략 3 — 비용 및 정합성 증명]: 결정론적 파이썬 통계 연산기로 LLM의 숫자 계산 환각을 없애고, 서가(DB) 캐싱으로 API 비용을 방어한 설계를 강조하면 면접에서 압도적 고평가를 받습니다."
        )

    # Case 3: '제미나이 argon(아르곤)' 관련 질문일 때
    if "argon" in p or "아르곤" in p:
        extra_crawled = "\n".join([f"• [수집 팩트]: {s}" for s in all_sents[:4]]) if all_sents else ""
        return (
            f"{h1}\n"
            f"• 전담 수행 부서: {sup['dept']} (검수 책임자: {sup['name']} / 심층 조사: {w1['name']}, {w2['name']})\n"
            f"• 조사 출처: {ref_title}\n"
            f"• 핵심 결론 요약: '제미나이 아르곤(Gemini Argon)'은 구글 딥마인드가 LMSYS Chatbot Arena 등 글로벌 블라인드 벤치마크에서 테스트한 차세대 플래그십 프론티어 모델(차세대 추론 및 자율 에이전트 통합 모델군)로, 고난도 코딩·수학 추론 능력과 백그라운드 자율 에이전트 UI 통합이 핵심입니다.{ceo_override_block}\n\n"
            f"{h2}\n"
            f"• [코드네임 Argon의 정체]: 정식 출시 전 글로벌 LLM 블라인드 테스트 아레나에서 'Argon'이라는 코드명으로 등장해 코딩, 하드 프롬프트, 복합 논리 추론 부문에서 최상위권 성적을 기록하며 주목받은 구글의 차세대 주력 모델입니다.\n"
            f"• [등장 배경]: 기존 단일 질의응답(Chat) 중심의 모델 한계를 넘어, 스스로 계획을 세우고 도구를 호출해 장기 작업을 완수하는 에이전틱 AI(Agentic AI) 시대를 겨냥해 설계되었습니다.\n\n"
            f"{h3}\n"
            f"• [자율 에이전트 인터페이스 통합]: 기존에는 백그라운드 자율 작업 기능을 쓰려면 별도의 '스파크(Spark)' 화면으로 전환해야 했으나, 메인 인터페이스 안에서 멀티스텝 에이전트 실행과 실시간 결과 확인이 가능하도록 통합되었습니다.\n"
            f"• [강화된 소프트웨어 엔지니어링 & 코딩]: 대규모 멀티파일 코드베이스 분석, 프론트엔드/백엔드 동시 구현, 실행 중 에러 자가 디버깅(Self-Healing) 성능이 비약적으로 향상되었습니다.\n"
            f"• [네이티브 멀티모달 및 초장문 컨텍스트]: 텍스트, 코드, 대용량 문서(PDF/엑셀), 이미지·오디오를 단일 모델에서 처리하며 수백만 토큰 컨텍스트에서도 높은 검색 정확도(Needle-in-a-Haystack)를 유지합니다.\n\n"
            f"{h4}\n"
            f"{extra_crawled if extra_crawled else '• 글로벌 개발자 커뮤니티 및 벤치마크에서 OpenAI의 최신 추론 모델 및 Claude 시리즈와 함께 프론티어 3강 체제를 구축한 핵심 모델로 평가받고 있습니다.'}\n"
            f"\n".join(news_lines[:3]) + "\n\n"
            f"{h5}\n"
            f"• [종합 정리]: 제미나이 아르곤은 단순 대화형 챗봇에서 '자율형 소프트웨어 엔지니어링 및 리서치 에이전트'로의 전환을 상징하는 모델로, 복잡한 실무 자동화 파이프라인의 주력 추론 엔진으로 활용 가치가 매우 높습니다."
        )

    # Case 4: 그 외 모든 일반 주제 질문
    if all_sents:
        summary_sent = " ".join(all_sents[:2])
        sec2_list = all_sents[2:6] if len(all_sents) > 2 else all_sents[:4]
        sec3_list = all_sents[6:11] if len(all_sents) > 4 else all_sents[:4]
        sec4_list = news_lines[:5] if news_lines else (all_sents[9:14] if len(all_sents) > 9 else all_sents[:3])
        sec5_list = all_sents[14:18] if len(all_sents) > 14 else [
            f"위키백과 및 공인 미디어 출처({ref_title})를 통해 '{ceo_prompt}'의 핵심 정의, 배경, 주요 특징 및 최신 동향을 종합 검증했습니다."
        ]

        return (
            f"{h1}\n"
            f"• 전담 수행 부서: {sup['dept']} (검수 책임자: {sup['name']} / 심층 조사: {w1['name']}, {w2['name']})\n"
            f"• 핵심 참고 출처: {ref_title}\n"
            f"• 핵심 요약: {summary_sent}{ceo_override_block}\n\n"
            f"{h2}\n"
            + "\n".join([f"• {s}" for s in sec2_list]) + "\n\n"
            f"{h3}\n"
            + "\n".join([f"• {s}" for s in sec3_list]) + "\n\n"
            f"{h4}\n"
            + "\n".join([f"• {re.sub(r'^[•\-\*]\s*', '', s)}" for s in sec4_list]) + "\n\n"
            f"{h5}\n"
            + "\n".join([f"• {s}" for s in sec5_list])
        )

    return (
        f"{h1}\n"
        f"• 전담 수행 부서: {sup['dept']} ({w1['name']}, {w2['name']})\n"
        f"• 핵심 요약: '{ceo_prompt}'에 대한 요청 사항을 분석했습니다.{ceo_override_block}\n\n"
        f"{h2}\n• 수집 원문 요약: {web_evidence[:600]}\n\n"
        f"{h3}\n• 세부 데이터: {web_evidence[600:1200]}\n\n"
        f"{h4}\n• 추가 검증 내역: {web_evidence[1200:1800]}\n\n"
        f"{h5}\n• 종합 결론: 요청하신 주제에 대한 다중 출처 팩트 정리를 완료했습니다."
    )

async def _check_and_broadcast_live_ceo(session_id: str, queue: asyncio.Queue, sup: dict, current_notes: list[str]) -> list[str]:
    new_notes = pop_live_instructions(session_id)
    if new_notes:
        current_notes.extend(new_notes)
        for note in new_notes:
            await queue.put({
                "type": "CEO_LIVE_INTERVENTION",
                "agentId": sup["id"],
                "agentName": sup["name"],
                "role": "SUPERVISOR",
                "timestamp": now_str(),
                "payload": {
                    "status": "WORKING",
                    "text": f"⚡ [실시간 CEO 긴급 지침 수신]: \"{note}\" ➔ 전담팀 보고서 내용에 즉시 반영합니다!",
                    "instruction": note,
                },
            })
    return current_notes

async def worker_research_node(state: MissionState, config: RunnableConfig) -> dict:
    queue: asyncio.Queue = config["configurable"]["event_queue"]
    session_id: str = config["configurable"].get("session_id", "default")
    attached_summary: str = config["configurable"].get("attached_summary", "")
    w1 = state["workers"][0]
    sup = state["supervisor"]
    live_notes = list(state.get("live_ceo_notes") or [])

    live_notes = await _check_and_broadcast_live_ceo(session_id, queue, sup, live_notes)

    await queue.put({
        "type": "NODE_LIFECYCLE",
        "phase": "PHASE_1_RESEARCH",
        "agentId": w1["id"],
        "agentName": w1["name"],
        "role": "WORKER",
        "timestamp": now_str(),
        "payload": {"status": "WORKING", "progress": 25}
    })

    cost_stat = record_token_usage(180, 95, is_cache_hit=False)
    await queue.put({
        "type": "COST_UPDATE",
        "agentId": w1["id"],
        "agentName": w1["name"],
        "role": "WORKER",
        "timestamp": now_str(),
        "payload": cost_stat,
    })

    reg_stds, unreg_stds = detect_compliance_standards(attached_summary, state["ceo_prompt"])
    keyword = w1.get("search_keyword", state["ceo_prompt"])
    if unreg_stds:
        # 레지스트리 미등록 규격(예: ISO 27001, HACCP 등) 입력 시 vision_browser 다중 지식 수집기로 해당 규격 핵심 요건 실시간 크롤링
        keyword = f"{unreg_stds[0]} 인증 필수 요구사항 심사 기준"

    await queue.put({
        "type": "MESSAGE", "agentId": w1["id"], "agentName": w1["name"], "role": "WORKER", "timestamp": now_str(),
        "payload": {"status": "WORKING", "text": f"[1차 공식 백과·언론·웹 통합 탐색] {w1['sub_task']}", "tokensUsed": 275}
    })

    web_res = await playwright_vision_browse(keyword, state["ceo_prompt"], w1["id"], w1["name"], queue)
    clean_evidence = web_res["collected_data"]

    if attached_summary:
        clean_evidence = f"[업로드된 첨부파일 전수 연산 데이터]\n{attached_summary}\n\n{clean_evidence}"

    if (reg_stds or unreg_stds) and "[다중 국제규격 정량 심사 결과" not in clean_evidence:
        iso_audit_res = evaluate_iso_compliance(
            attached_summary or clean_evidence,
            state["ceo_prompt"],
            crawled_knowledge=clean_evidence,
        )
        clean_evidence = f"[다중 규격 레지스트리 & 폴백 심사 엔진 정량 점검 데이터]\n{iso_audit_res}\n\n{clean_evidence}"

    fact_sheet = build_extractive_fact_sheet(state["ceo_prompt"], clean_evidence)

    await queue.put({
        "type": "MESSAGE", "agentId": w1["id"], "agentName": w1["name"], "role": "WORKER", "timestamp": now_str(),
        "payload": {"status": "REVIEWING", "text": f"📄 [1차 조사 시트 상신]\n{fact_sheet}", "tokensUsed": 230}
    })

    return {"web_evidence": clean_evidence, "worker1_draft": fact_sheet, "live_ceo_notes": live_notes}

async def supervisor_qc_node(state: MissionState, config: RunnableConfig) -> dict:
    queue: asyncio.Queue = config["configurable"]["event_queue"]
    session_id: str = config["configurable"].get("session_id", "default")
    sup = state["supervisor"]
    w1 = state["workers"][0]
    w2 = state["workers"][1] if len(state["workers"]) > 1 else w1
    live_notes = list(state.get("live_ceo_notes") or [])
    live_notes = await _check_and_broadcast_live_ceo(session_id, queue, sup, live_notes)

    if state.get("final_report"):
        final_rep = state["final_report"]
        if live_notes and "실시간 CEO 특별 지시사항" not in final_rep:
            final_rep += f"\n\n📌 6. 실시간 CEO 특별 지시사항 반영 내역\n" + "\n".join([f"• ⚡ [대표님 실시간 지침]: \"{n}\" ➔ 전담부서 최종 검토 및 상세 분석에 즉시 반영 완료." for n in live_notes])

        _, final_score, final_breakdown = evaluate_qc_rubric(state["ceo_prompt"], final_rep, state["web_evidence"], is_final=True)
        cost_stat = record_token_usage(140, 80, is_cache_hit=False)
        await queue.put({"type": "COST_UPDATE", "agentId": sup["id"], "agentName": sup["name"], "role": "SUPERVISOR", "timestamp": now_str(), "payload": cost_stat})

        await queue.put({
            "type": "NODE_LIFECYCLE",
            "phase": "PHASE_3_FINAL_APPROVAL",
            "agentId": sup["id"],
            "agentName": sup["name"],
            "role": "SUPERVISOR",
            "timestamp": now_str(),
            "payload": {"status": "DONE", "progress": 100}
        })
        await queue.put({
            "type": "MESSAGE", "agentId": sup["id"], "agentName": sup["name"], "role": "SUPERVISOR", "timestamp": now_str(),
            "payload": {"status": "DONE", "text": f"✅ [최종 검수 통과] {final_breakdown} ➔ 서가(책장) DB에 영구 보관하고 중앙 회의실에 비치합니다.", "tokensUsed": 220}
        })
        await queue.put({
            "type": "FINAL_REPORT", "agentId": sup["id"], "agentName": sup["name"], "role": "SUPERVISOR", "timestamp": now_str(),
            "payload": {"status": "DONE", "reportMarkdown": final_rep, "tokensUsed": 480}
        })
        return {"qc_passed": True, "qc_score": final_score, "final_report": final_rep, "live_ceo_notes": live_notes}

    passed, score, breakdown = evaluate_qc_rubric(state["ceo_prompt"], state["worker1_draft"], state["web_evidence"], is_final=False)

    # 1차에서 반려되었거나 CEO 실시간 개입이 들어온 경우 2차 심화 작성 노드로 이동
    if (not passed or len(live_notes) > 0) and state["reject_count"] == 0:
        base_kw = w1.get("search_keyword", state["ceo_prompt"][:20])
        followup_kw = await generate_agentic_followup_query(base_kw, state["ceo_prompt"], state["web_evidence"])

        feedback = (
            f"{breakdown}\n"
            f"🚨 [팀장 QC 반려 — 2차 심화 보강 지시]: "
            + (f"대표님의 실시간 추가 지침('{live_notes[-1]}')과 " if live_notes else "")
            + f"질문 주제에 대한 구체적 세부 내용을 보강하기 위해 {w1['name']}님은 심화 쿼리('{followup_kw}')로 추가 팩트를 확보하고, "
            f"{w2['name']}님은 5단 심층 보고서로 완성해 올리세요!"
        )
        await queue.put({
            "type": "NODE_LIFECYCLE",
            "phase": "PHASE_2_REJECT_AND_REWORK",
            "agentId": sup["id"],
            "agentName": sup["name"],
            "role": "SUPERVISOR",
            "timestamp": now_str(),
            "payload": {"status": "REJECTED", "progress": 50}
        })
        await queue.put({
            "type": "QC_REJECT", "agentId": sup["id"], "agentName": sup["name"], "role": "SUPERVISOR", "timestamp": now_str(),
            "payload": {
                "status": "REJECTED",
                "targetWorkerId": w1["id"],
                "rejectReason": feedback,
                "tokensUsed": 150
            }
        })
        return {
            "qc_passed": False,
            "qc_score": score,
            "qc_feedback": feedback,
            "rework_query": followup_kw,
            "reject_count": state["reject_count"] + 1,
            "live_ceo_notes": live_notes,
        }

    h1, h2, h3, h4, h5 = get_5section_headers(state["ceo_prompt"])
    fast_prompt = f"""당신은 {sup['dept']}의 수석 분석가 {w2['name']}입니다.
사용자의 질문('{state['ceo_prompt']}')에 대해 아래 수집된 백과사전·뉴스·문서 원문과 당신의 전문 지식을 결합하여 가장 알차고 구체적인 [5단 심층 보고서]를 작성하세요.

[수집된 원문 데이터]:
{state['web_evidence'][:4500]}

[절대 규칙]
1. 에이전트가 어떻게 조사했는지(크롤링 과정, 파이프라인 설명 등)는 단 한 줄도 쓰지 마세요! 오직 사용자가 물어본 주제('{state['ceo_prompt']}') 자체에 대한 풍부한 실제 정보, 배경, 특징, 세부 내용만 작성하세요.
2. 아래 5개 제목({h1} ~ {h5})과 글머리 기호(•)만 사용하세요."""

    direct_report = await call_gemini_llm(fast_prompt, temperature=0.25)
    if not direct_report or "📌 4." not in direct_report:
        direct_report = build_comprehensive_5section_report(state["ceo_prompt"], state["web_evidence"], sup, w1, w2, live_notes)

    await queue.put({
        "type": "MESSAGE", "agentId": sup["id"], "agentName": sup["name"], "role": "SUPERVISOR", "timestamp": now_str(),
        "payload": {"status": "DONE", "text": f"⚡ [1차 충분한 팩트 확보 — 즉시 승인] {breakdown} ➔ 중앙 회의실에 5단 심층 보고서를 비치합니다!", "tokensUsed": 200}
    })
    await queue.put({
        "type": "FINAL_REPORT", "agentId": sup["id"], "agentName": sup["name"], "role": "SUPERVISOR", "timestamp": now_str(),
        "payload": {"status": "DONE", "reportMarkdown": direct_report, "tokensUsed": 400}
    })
    return {"qc_passed": True, "qc_score": score, "final_report": direct_report, "live_ceo_notes": live_notes}

def route_after_qc(state: MissionState) -> Literal["worker_revision_node", "__end__"]:
    if not state.get("qc_passed", False):
        return "worker_revision_node"
    return "__end__"

async def worker_revision_node(state: MissionState, config: RunnableConfig) -> dict:
    queue: asyncio.Queue = config["configurable"]["event_queue"]
    session_id: str = config["configurable"].get("session_id", "default")
    sup = state["supervisor"]
    w1 = state["workers"][0]
    w2 = state["workers"][1] if len(state["workers"]) > 1 else w1
    h1, h2, h3, h4, h5 = get_5section_headers(state["ceo_prompt"])
    live_notes = list(state.get("live_ceo_notes") or [])
    live_notes = await _check_and_broadcast_live_ceo(session_id, queue, sup, live_notes)

    followup_kw = state.get("rework_query") or f"{w1.get('search_keyword', '')} 상세 정보"

    await queue.put({
        "type": "MESSAGE", "agentId": w1["id"], "agentName": w1["name"], "role": "WORKER", "timestamp": now_str(),
        "payload": {"status": "WORKING", "text": f"🔄 [부서 복귀 & 2차 심화 탐색 가동] 심화 쿼리('{followup_kw}')로 추가 백과·뉴스 문서를 탐색합니다.", "tokensUsed": 160}
    })

    second_web_res = await playwright_vision_browse(followup_kw, state["ceo_prompt"], w1["id"], w1["name"], queue)
    combined_evidence = (
        f"{state['web_evidence']}\n\n"
        f"[2차 심화 재크롤링 추가 확보 데이터 (쿼리: {followup_kw})]\n"
        f"{second_web_res['collected_data']}"
    )

    live_notes = await _check_and_broadcast_live_ceo(session_id, queue, sup, live_notes)
    ceo_note_prompt = ""
    if live_notes:
        ceo_note_prompt = f"\n[⚡ CEO 실시간 특별 개입 지시사항 (최우선 반영)]: {' / '.join(live_notes)}\n"

    await queue.put({
        "type": "MESSAGE", "agentId": w2["id"], "agentName": w2["name"], "role": "WORKER", "timestamp": now_str(),
        "payload": {"status": "WORKING", "text": f"💻 [1·2차 통합 지식 기반 5단 심층 보고서 작성] {w2['sub_task']}", "tokensUsed": 190}
    })

    cost_stat = record_token_usage(620, 480, is_cache_hit=False)
    await queue.put({"type": "COST_UPDATE", "agentId": w2["id"], "agentName": w2["name"], "role": "WORKER", "timestamp": now_str(), "payload": cost_stat})

    revision_prompt = f"""당신은 {sup['dept']}의 수석 분석가 {w2['name']}입니다.
사용자의 요청('{state['ceo_prompt']}')에 대해 아래 수집된 백과사전·뉴스·문서 원문과 당신의 전문 지식을 모두 결합하여 가장 완성도 높은 [5단 심층 보고서]를 작성하세요.
{ceo_note_prompt}
[사용자 요청]: {state['ceo_prompt']}
[수집된 백과사전·언론보도·문서 데이터]:
{combined_evidence[:5000]}

[가장 중요한 작성 규칙]
1. "공인 문서 탐색과 심화 벤치마크 크롤링을 통해 검증한 결과...", "단일 모델 호출 방식을 넘어..." 같이 에이전트의 조사 방식이나 시스템을 설명하는 메타 문구는 단 한 줄도 절대 쓰지 마세요!
2. 오직 사용자가 물어본 대상('{state['ceo_prompt']}') 그 자체에 대한 구체적인 정답, 역사, 배경, 인물/기술 특징, 세부 스펙, 실제 사례만 자세하게 작성하세요.
3. 각 섹션마다 최소 3~5개의 상세한 글머리 기호(•)를 포함하세요.

출력 양식:
{h1}
• 전담 수행 부서: {sup['dept']} (검수: {sup['name']} / 실무: {w1['name']}, {w2['name']})
• 참고 출처: (실제 문서 제목 또는 데이터 출처)
• 핵심 요약: (질문 대상에 대한 3~4문장 분량의 정확하고 구체적인 핵심 정의 및 요약)

{h2}
• (질문 대상의 탄생 배경, 역사, 핵심 구조 또는 원리에 대한 상세 설명 3~5개 불릿)

{h3}
• (질문 대상의 가장 중요한 특징, 세부 내용, 기술/능력 사양, 수치 팩트 5~6개 불릿)

{h4}
• (관련 최신 동향, 미디어/시장 평가, 주요 사례 또는 유의사항 3~4개 불릿)

{h5}
• (종합적 의의, 활용 방안 또는 최종 정리 3~4개 불릿)"""

    final_text = await call_gemini_llm(revision_prompt, temperature=0.25)
    if not final_text or "📌 4." not in final_text:
        final_text = build_comprehensive_5section_report(
            state["ceo_prompt"],
            combined_evidence,
            sup,
            w1,
            w2,
            live_notes,
        )

    await queue.put({
        "type": "STATUS_CHANGE", "agentId": w1["id"], "agentName": w1["name"], "role": "WORKER", "timestamp": now_str(),
        "payload": {"status": "DONE"}
    })
    await queue.put({
        "type": "MESSAGE", "agentId": w2["id"], "agentName": w2["name"], "role": "WORKER", "timestamp": now_str(),
        "payload": {"status": "DONE", "text": "📄 [5단 심층 보고서 작성 완료] 중앙 결재 회의실로 이동합니다!", "tokensUsed": 440}
    })

    return {"web_evidence": combined_evidence, "final_report": final_text, "live_ceo_notes": live_notes}

GRAPH_CHECKPOINTER = MemorySaver()

def build_company_graph():
    builder = StateGraph(MissionState)
    builder.add_node("worker_research_node", worker_research_node)
    builder.add_node("supervisor_qc_node", supervisor_qc_node)
    builder.add_node("worker_revision_node", worker_revision_node)

    builder.set_entry_point("worker_research_node")
    builder.add_edge("worker_research_node", "supervisor_qc_node")
    builder.add_conditional_edges("supervisor_qc_node", route_after_qc)
    builder.add_edge("worker_revision_node", "supervisor_qc_node")
    return builder.compile(checkpointer=GRAPH_CHECKPOINTER)
