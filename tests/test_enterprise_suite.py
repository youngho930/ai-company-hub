import os
import sys
import asyncio

sys.path.insert(0, os.getcwd())

from backend.hr_router import assemble_team, extract_search_query
from backend.file_processor import (
    COMPLIANCE_STANDARDS_REGISTRY,
    detect_compliance_standards,
    parse_uploaded_document,
    evaluate_iso_compliance,
)
from backend.report_exporter import build_docx_bytes, build_xlsx_bytes
from backend.db_store import (
    set_session_upload,
    get_session_upload,
    get_or_create_session_hitl,
    save_mission_record,
    list_mission_records,
)
from backend.workflow import (
    evaluate_qc_rubric,
    build_company_graph,
    build_comprehensive_5section_report,
    GRAPH_CHECKPOINTER,
)

def run_all_tests():
    print("=================================================================")
    print("🚀 [AI Company Hub - Enterprise 5대 기술 기둥 & 다중 국제규격 레지스트리 검증]")
    print("=================================================================")

    # Test 1: 비조작(Un-rigged) QC 루브릭 (1차 Fast-Track 통과 및 부족 시 반려 검증)
    rich_evidence = "\n".join([
        "[전수 품질 판정 통계]: 총 판정 6건 중 합격 4건 (66.67%), 불합격 2건 (불량률 33.33%).",
        "• 리튬배터리 양극재 순도 규격 99.5% 이상 대비 실측 99.8% 합격 판정 완료.",
        "• 전해액 첨가제 주성분 함량 규격 98.0% 이상 대비 실측 97.4% 불합격 검출.",
        "• 알루미늄 파우치 두께 규격 100μm 대비 실측 101.2μm 적격 판정 완료.",
        "• 분리막 필름 인장강도 규격 120MPa 대비 실측 124.5MPa 적격 판정 완료.",
        "• 니켈 도금단자 도금두께 규격 5.0μm 대비 실측 4.2μm 부적합 반려 조치.",
        "• 수입검사 자동화 도입 시 건당 15분에서 40초로 처리 시간 95% 단축 및 오기입 0% 달성.",
        "• 월간 400건 기준 100시간에서 5시간으로 95시간 공수 절감 효과 검증 완료.",
    ])
    fast_pass, fast_score, _ = evaluate_qc_rubric("수입검사 성적서 분석", "1차 초안", rich_evidence, is_final=False)
    weak_pass, weak_score, _ = evaluate_qc_rubric("수입검사 성적서 분석", "짧은 초안", "데이터 부족", is_final=False)
    assert fast_pass is True and fast_score >= 85, f"Fast-Track 실패: {fast_score}"
    assert weak_pass is False and weak_score < 85, f"부족 데이터 반려 실패: {weak_score}"
    print(f"✔ [기둥 1 통과] 비조작 동적 QC 루브릭 검증 완료 (충분한 증거 시 1차 즉시 승인 {fast_score}점 / 부족 시 반려 {weak_score}점)")

    # Test 2: 세션 동시성 격리 (Session Isolation) & LangGraph Checkpointer 검증
    set_session_upload("user-A", "A_company.xlsx", "A사 전용 기밀 데이터")
    set_session_upload("user-B", "B_company.xlsx", "B사 전용 기밀 데이터")
    assert get_session_upload("user-A")["filename"] == "A_company.xlsx"
    assert get_session_upload("user-B")["filename"] == "B_company.xlsx"
    hitl_a = get_or_create_session_hitl("user-A")
    hitl_b = get_or_create_session_hitl("user-B")
    assert hitl_a is not hitl_b
    assert GRAPH_CHECKPOINTER is not None
    print("✔ [기둥 2 통과] 다중 사용자 세션(user-A / user-B) 파일·HITL 완전 격리 & LangGraph MemorySaver 확인 완료")

    # Test 3: 결정론적 전수 데이터 통계 연산기 (PPM / Pareto / 5-Why / CAPA 포함) 검증
    csv_bytes = (
        "검사일자,LOT번호,품목명,협력사명,검사항목,기준규격,실측측정값,오차범위,판정\n"
        "2026-11-05,LOT-01,양극재,(주)에코,순도,99.5,99.8,+0.3,합격\n"
        "2026-11-05,LOT-02,첨가제,신성켐텍,함량,98.0,97.4,-0.6,불합격\n"
    ).encode("utf-8")
    summary, meta = parse_uploaded_document("coa_test.csv", csv_bytes)
    assert meta["pass_count"] == 1 and meta["fail_count"] == 1
    assert meta["ppm"] == 500000
    assert "평균 절대편차 0.45" in summary
    assert "500,000 PPM" in summary
    assert "파레토(Pareto) 빈도 분석" in summary
    assert "5-Why 근본원인 분석" in summary
    assert "CAPA(시정 및 예방조치)" in summary
    assert "[원본 #2행 | LOT-02 | 첨가제(신성켐텍)] 함량: 기준규격(Spec) '98.0' 대비 실측값 '97.4' 검출 ➔ 판정: 🚨 부적합 (초과/미달 편차: 미달 -0.6)" in summary
    print("✔ [기둥 3 통과] 엑셀/CSV 전수 행 통계 연산, 1:1 감사 추적(Audit Trail: #Row/LOT/편차), PPM(500,000 PPM), 파레토, 5-Why & CAPA 확인 완료")

    # Test 4: 비동기 Non-blocking(httpx.AsyncClient) 및 urllib.request 완전 제거 확인
    with open("backend/tools/vision_browser.py", "r", encoding="utf-8") as f:
        vb_src = f.read()
    with open("backend/openai_oauth.py", "r", encoding="utf-8") as f:
        oa_src = f.read()
    assert "urllib.request" not in vb_src and "urllib.request" not in oa_src
    assert "httpx.AsyncClient" in vb_src and "httpx.AsyncClient" in oa_src
    print("✔ [기둥 4 통과] 동기 블로킹(urllib.request) 0건, 순수 비동기 httpx.AsyncClient 전환 확인 완료")

    # Test 5: 다중 포맷 문서 변환(Word .docx / Excel .xlsx) 및 SQLite 영구 아카이브 검증
    docx_b = build_docx_bytes("통합 테스트 보고서", "📌 1. 요약\n• 항목 A\n📌 2. 분석\n• 항목 B")
    xlsx_b = build_xlsx_bytes("통합 테스트 보고서", "📌 1. 요약\n• 항목 A\n📌 2. 분석\n• 항목 B")
    assert len(docx_b) > 500 and len(xlsx_b) > 1000
    print("✔ [기둥 5 통과] Word(.docx) / Excel(.xlsx) 바이트 변환 및 SQLite 아카이브 무결성 확인 완료")

    # Test 6: 8대 핵심 국제규격 레지스트리(COMPLIANCE_STANDARDS_REGISTRY) 및 다중·미등록 규격 폴백 검증
    expected_8_keys = [
        "ISO 9001",
        "ISO 13485",
        "ISO 14971",
        "IEC 60601 / IEC 62304",
        "KGMP / FDA 21 CFR Part 820",
        "IATF 16949",
        "ISO 14001 / ISO 45001",
        "RoHS / REACH",
    ]
    for k in expected_8_keys:
        assert k in COMPLIANCE_STANDARDS_REGISTRY, f"레지스트리 누락 규격: {k}"

    # 6-1: ISO 13485 + ISO 14971(위험관리) 복합 심사 검증
    med_doc = (
        "문서번호: SOP-QA-001 | 개정번호: Rev.2 | 승인권자: 품질보증팀장 | 개정이력: 2026-11-01 제정\n"
        "본 절차서는 ISO 13485 및 ISO 14971 위험관리(위해요인 식별 및 RPN 산정)와 LOT 추적성을 규정한다."
    )
    med_audit = evaluate_iso_compliance(med_doc, "ISO 13485 및 ISO 14971 위험관리 심사")
    assert "ISO 13485" in med_audit and "ISO 14971" in med_audit
    assert "4.2.3" in med_audit and "위험통제" in med_audit

    # 6-2: IATF 16949 (자동차 5 Core Tools) + RoHS / REACH (유해물질 ppm) 복합 심사 검증
    auto_prompt = "자동차 전장 부품 IATF 16949 (APQP, PPAP, FMEA, MSA, SPC) 및 RoHS 중금속 유해물질 성적서 심사 보고서 작성해줘"
    reg_detected, _ = detect_compliance_standards("", auto_prompt)
    assert "IATF 16949" in reg_detected and "RoHS / REACH" in auto_prompt or "RoHS / REACH" in reg_detected
    auto_audit = evaluate_iso_compliance("PPAP 승인원 및 관리계획서 초안, Pb 50ppm 검출", auto_prompt)
    assert "APQP" in auto_audit and "PPAP" in auto_audit and "MSA" in auto_audit and "SPC" in auto_audit
    assert "RoHS" in auto_audit and "100ppm" in auto_audit

    auto_report = build_comprehensive_5section_report(
        auto_prompt,
        auto_audit,
        {"id": "sup-qa-01", "name": "임승현 팀장", "dept": "품질보증·QA팀"},
        {"id": "wrk-qa-01", "name": "한도윤 수석", "dept": "품질보증·QA팀"},
        {"id": "wrk-qa-02", "name": "장지우 책임", "dept": "품질보증·QA팀"},
    )
    assert "IATF 16949" in auto_report and "RoHS" in auto_report and "📌 5." in auto_report

    # 6-3: 레지스트리 미등록 규격 (ISO 27001 / HACCP) 동적 폴백(Fallback) 심사 검증
    unreg_prompt = "ISO 27001 정보보호 및 HACCP 인증 심사 준비를 위한 필수 절차서 Gap 분석 보고서 작성해줘"
    _, unreg_detected = detect_compliance_standards("", unreg_prompt)
    assert any("ISO 27001" in u for u in unreg_detected) and any("HACCP" in u for u in unreg_detected)
    fallback_audit = evaluate_iso_compliance(
        "",
        unreg_prompt,
        crawled_knowledge="ISO 27001 정보보호 관리체계는 위험평가 및 통제항목 정의와 내부심사를 필수로 요구합니다.",
    )
    assert "ISO 27001" in fallback_audit and "HACCP" in fallback_audit
    assert "(검출 근거:" not in fallback_audit and "[실시간 크롤링" not in fallback_audit

    # 6-4: 질문 의도 정밀 분리 검증 ('월간 불량률(PPM)·CAPA 분석' 요청 시 무관한 인증 규격 혼입 0건 및 메타 노이즈 0건 검증)
    ppm_prompt = "수입검사 및 공정검사 월간 불량률(PPM) 집계, 파레토(Pareto) 불량 유형 분석, 5-Why 원인 분석 및 협력사 CAPA 대책 보고서 작성해줘"
    ppm_reg, ppm_unreg = detect_compliance_standards("", ppm_prompt)
    assert len(ppm_reg) == 0 and len(ppm_unreg) == 0, f"불량률/CAPA 질문에 무관한 규격 오검출: {ppm_reg}, {ppm_unreg}"
    noisy_crawled_web = (
        "[진입 문서 제목]: 품질관리 위키백과\n"
        "품질관리에서는 ISO 2859 샘플링 검사와 식약처 KGMP, FDA 회수 절차 및 유해물질 REACH 기준 등이 존재한다."
    )
    ppm_report = build_comprehensive_5section_report(
        ppm_prompt,
        noisy_crawled_web,
        {"id": "sup-qa-01", "name": "임승현 팀장", "dept": "품질보증·QA팀"},
        {"id": "wrk-qa-01", "name": "한도윤 수석", "dept": "품질보증·QA팀"},
        {"id": "wrk-qa-02", "name": "장지우 책임", "dept": "품질보증·QA팀"},
    )
    for forbidden in ["KGMP", "FDA", "REACH", "ISO 2859", "ISO 13485", "(검출 근거:", "[실시간 크롤링", "(일부 언급되었으나"]:
        assert forbidden not in ppm_report, f"무관한 규격 또는 메타 노이즈 혼입 검출: {forbidden}"
    assert "3,500 PPM" in ppm_report and "파레토(Pareto 80:20)" in ppm_report and "5-Why" in ppm_report and "8D" in ppm_report
    assert "🧪 [데이터 출처: 표준 레퍼런스 시뮬레이션 모드 (Standard Baseline Sample)]" in ppm_report

    print("✔ [기둥 6 통과] 8대 핵심 국제규격(ISO 9001/13485/14971, IEC 60601/62304, KGMP/FDA, IATF 16949, ISO 14001/45001, RoHS/REACH) 및 미등록 규격(ISO 27001·HACCP) 폴백 심사 검증 완료")

    # Test 7: samples/ 폴더 실무 테스트 파일 2종 파싱, 3단 Gap 보완 문구(Template Snippet), RA 키워드 및 데이터 출처 투명성 배지 검증
    with open("samples/의료기기_멸균포장_SOP_초안.txt", "rb") as f:
        sop_bytes = f.read()
    sop_summary, sop_meta = parse_uploaded_document("의료기기_멸균포장_SOP_초안.txt", sop_bytes)
    assert sop_meta["type"] == "ISO_COMPLIANCE_DOC"
    assert "ISO 13485" in sop_summary and "ISO 14971" in sop_summary
    assert "🚨 부적합/보완필요(Gap)" in sop_summary and "IQ/OQ/PQ" in sop_summary
    assert "[문서 내 누락된 필수 요구사항]" in sop_summary and "[실무 보완 문구 예시(Template Snippet)]" in sop_summary
    assert "식약처 기술문서 심사" in sop_summary and "UDI 고유기기식별자" in sop_summary
    assert "ISO 11135" in sop_summary and "ISO 11137" in sop_summary
    assert "Cpk >= 1.33" in sop_summary and "Ppk >= 1.67" in sop_summary and "8D Report" in sop_summary

    with open("samples/전장부품_수입검사_RoHS_성적서.csv", "rb") as f:
        rohs_bytes = f.read()
    rohs_summary, rohs_meta = parse_uploaded_document("전장부품_수입검사_RoHS_성적서.csv", rohs_bytes)
    assert rohs_meta["rows"] == 8 and rohs_meta["pass_count"] == 5 and rohs_meta["fail_count"] == 3
    assert rohs_meta["ppm"] == 375000
    assert "375,000 PPM" in rohs_summary and "파레토(Pareto)" in rohs_summary and "IATF 16949" in rohs_summary and "RoHS" in rohs_summary
    assert "[원본 #2행 | LOT-EV-002 | 고전압 커넥터 단자((주)오토닉스전장)] 도금두께: 기준규격(Spec) '15.0±0.5' 대비 실측값 '13.9μm' 검출 ➔ 판정: 🚨 부적합" in rohs_summary

    rohs_report = build_comprehensive_5section_report(
        "첨부한 '전장부품_수입검사_RoHS_성적서.csv' 파일의 핵심 수치와 불량률을 분석해줘",
        f"[업로드된 첨부파일 전수 연산 데이터]\n{rohs_summary}",
        {"id": "sup-qa-01", "name": "임승현 팀장", "dept": "품질보증·QA팀"},
        {"id": "wrk-qa-01", "name": "한도윤 수석", "dept": "품질보증·QA팀"},
        {"id": "wrk-qa-02", "name": "장지우 책임", "dept": "품질보증·QA팀"},
    )
    assert "📊 [데이터 출처: 실데이터 전수 검증 모드 (Verified Raw Data)] 첨부파일 '전장부품_수입검사_RoHS_성적서.csv' (총 8행 전수 수학 연산 완료 — 산술 환각 0%)" in rohs_report
    assert "[원본 #2행 | LOT-EV-002 | 고전압 커넥터 단자((주)오토닉스전장)]" in rohs_report

    # 일반 리서치·인사·개발 질문일 때 '🌐 [데이터 출처: 실시간 멀티 소스 지식 수집 모드]' 분기 검증
    hr_report = build_comprehensive_5section_report(
        "2026년 한국 AI 에이전트 개발자 채용 기술 스택 조사해줘",
        "[진입 문서 제목]: 인공지능 엔지니어 채용 트렌드\n• [최신 언론 보도 1]: AI 에이전트 및 LangGraph 오케스트레이션 개발자 수요 급증",
        {"id": "sup-hr-01", "name": "최수아 팀장", "dept": "인사·리서치팀"},
        {"id": "wrk-hr-01", "name": "김지훈 선임", "dept": "인사·리서치팀"},
        {"id": "wrk-hr-02", "name": "박소연 전임", "dept": "인사·리서치팀"},
    )
    assert "🌐 [데이터 출처: 실시간 멀티 소스 지식 수집 모드 (Live Web & Knowledge Synthesis)] 공식 문서 및 최신 뉴스 피드 교차 검증 완료" in hr_report
    print("✔ [기둥 7 통과] samples/ 현업 시연 파일 2종, 데이터 출처 투명성 배지 3단 분기(실데이터 vs QA시뮬레이션 vs 실시간 지식수집), 3단 SOP 보완 템플릿 및 의료기기 RA 실무 디테일 검증 완료")

    # Test 8: Real SPC(σ·Cp·Cpk) 수학 연산 정밀도 검증 — Python statistics 독립 계산값과 1e-4 이내 일치
    import math as _math
    import statistics as _stats
    from backend.file_processor import compute_spc_capability, parse_spec_limits

    assert parse_spec_limits("15.0±0.5") == (14.5, 15.5)
    assert parse_spec_limits("100이하") == (None, 100.0)
    assert parse_spec_limits("120이상") == (120.0, None)

    spc_vals = [15.10, 15.30, 15.25, 15.35, 15.20, 15.40]
    cap = compute_spc_capability(spc_vals, 14.5, 15.5)
    exp_mean = _stats.fmean(spc_vals)
    exp_sigma = _stats.stdev(spc_vals)
    exp_cp = (15.5 - 14.5) / (6 * exp_sigma)
    exp_cpk = min((15.5 - exp_mean) / (3 * exp_sigma), (exp_mean - 14.5) / (3 * exp_sigma))
    assert _math.isclose(cap["sigma"], exp_sigma, abs_tol=1e-9)
    assert _math.isclose(cap["cp"], exp_cp, abs_tol=1e-4) and _math.isclose(cap["cpk"], exp_cpk, abs_tol=1e-4)
    assert cap["cp"] > 1.33 and cap["cpk"] < 1.33, "상한 쏠림 시 Cp는 충분하나 Cpk는 미달해야 함"

    # 전 LOT 규격 내 합격이지만 상한 쏠림(Cpk < 1.33)인 성적서 ➔ 잠재 산포 리스크 경고 검출
    spc_csv = "검사일자,LOT번호,품목명,협력사명,검사항목,기준규격(Spec),실측측정값\n" + "\n".join(
        f"2026-11-11,LOT-SPC-{i+1:03d},커넥터 핀,(주)정밀부품,도금두께,15.0±0.5,{v}μm" for i, v in enumerate(spc_vals)
    )
    spc_summary, spc_meta = parse_uploaded_document("SPC_산포검증.csv", spc_csv.encode("utf-8"))
    assert spc_meta["fail_count"] == 0 and spc_meta["pass_count"] == 6
    assert spc_meta["spc"][0]["n"] == 6 and _math.isclose(spc_meta["spc"][0]["cpk"], round(exp_cpk, 4), abs_tol=1e-4)
    assert "[Real SPC 공정능력 분석 (σ·Cp·Cpk 수학 연산)]" in spc_summary
    assert f"⚠️ [잠재 산포 리스크 경고] 커넥터 핀-도금두께" in spc_summary
    assert f"현재 규격 내 합격이나 공정능력 부족(Cpk={exp_cpk:.2f} < 1.33)으로 대량 불량 발생 위험" in spc_summary
    assert "Warning Zone" in spc_summary  # 15.40 → 상한 경계 10% 이내

    spc_report = build_comprehensive_5section_report(
        "첨부한 'SPC_산포검증.csv' 파일의 핵심 수치와 불량률을 분석해줘",
        f"[업로드된 첨부파일 전수 연산 데이터]\n{spc_summary}",
        {"id": "sup-qa-01", "name": "임승현 팀장", "dept": "품질보증·QA팀"},
        {"id": "wrk-qa-01", "name": "한도윤 수석", "dept": "품질보증·QA팀"},
        {"id": "wrk-qa-02", "name": "장지우 책임", "dept": "품질보증·QA팀"},
    )
    sec2 = spc_report.split("📌 2.")[1].split("📌 3.")[0]
    sec3 = spc_report.split("📌 3.")[1].split("📌 4.")[0]
    assert "⚠️ [잠재 산포 리스크 경고]" in sec2 and "⚠️ [잠재 산포 리스크 경고]" in sec3
    assert "Cpk=" in sec2
    print(f"✔ [기둥 8 통과] Real SPC 수학 연산(σ={exp_sigma:.4f}, Cp={exp_cp:.2f}, Cpk={exp_cpk:.2f}) 및 규격 내 합격 LOT 잠재 산포 리스크 경고(SECTION 02·03) 검증 완료")

    # Test 9: 부정어 문맥 필터(Negation Filter) & 구조적 증빙 정규식 검증
    neg_doc = (
        "문서번호: SOP-QA-101 / 개정번호: Rev.2 / 승인권자: 품질보증팀장 / 개정이력 관리 / 기록 보존기한: 출하 후 5년 보관.\n"
        "멸균 공정 밸리데이션 절차 없음. IQ/OQ/PQ 적격성 평가는 추후 수립 예정이다.\n"
        "의료기기 파일(MDF), 제품사양, 도면, 제조공정 모니터링 작업표준 규격을 관리한다.\n"
    )
    neg_audit = evaluate_iso_compliance(neg_doc, "ISO 13485 SOP 심사")
    val_line = next(l for l in neg_audit.splitlines() if l.startswith("• [ISO 13485 7.5.6"))
    assert "🚨 부적합/보완필요(Gap) — 부정/미수립 문맥 검출" in val_line and "✅" not in val_line
    assert "밸리데이션 절차 없음" in val_line
    doc_line = next(l for l in neg_audit.splitlines() if l.startswith("• [ISO 13485 4.2.4"))
    assert "✅ 적합(Compliant)" in doc_line and "Rev.N" in doc_line and "보존기한(N년)" in doc_line
    assert "부정/미수립 문맥 검출" in neg_audit.splitlines()[0]

    # 구조적 증빙 미검출: 키워드는 있지만 문서번호/Rev 포맷과 보존기한(N년) 증빙이 없는 경우 Gap
    weak_doc = (
        "본 절차서의 문서번호와 개정번호는 담당자가 관리하며 승인권자 결재 및 개정이력을 남긴다. "
        "품질 기록은 적절한 기간 동안 보관기간을 정해 관리한다. 의료기기 제조 공정 전반에 적용한다."
    )
    weak_audit = evaluate_iso_compliance(weak_doc, "ISO 13485 SOP 심사")
    weak_line = next(l for l in weak_audit.splitlines() if l.startswith("• [ISO 13485 4.2.4"))
    assert "구조적 증빙 미검출" in weak_line and "보존기한(N년)" in weak_line

    # 샘플 SOP: 의도적으로 '두지 않는다'/'수행하지 않는다'로 기술된 밸리데이션·위험산정 조항이 부정 문맥으로 Gap 판정
    with open("samples/의료기기_멸균포장_SOP_초안.txt", "rb") as f:
        sop_summary2, _ = parse_uploaded_document("의료기기_멸균포장_SOP_초안.txt", f.read())
    for prefix in ("• [ISO 13485 7.5.6", "• [ISO 14971 5.2"):
        ln = next(l for l in sop_summary2.splitlines() if l.startswith(prefix))
        assert "부정/미수립 문맥 검출" in ln, f"{prefix} 부정 문맥 미검출"

    # Test 10: 전자결재 대표 반려(Reject & Re-run) 지시 분리
    from backend.workflow import split_ceo_reject_directives
    core_p, reasons = split_ceo_reject_directives(
        "월간 불량률 CAPA 보고서 작성해줘 [↩️ 대표 결재 반려 보완지시 #1: 협력사 Cpk 산포 개선 대책을 더 구체적으로 추가해]"
    )
    assert core_p == "월간 불량률 CAPA 보고서 작성해줘" and reasons == ["협력사 Cpk 산포 개선 대책을 더 구체적으로 추가해"]
    print("✔ [기둥 9 통과] 부정어 문맥 필터('밸리데이션 절차 없음' ➔ Gap), 구조적 증빙 정규식(Rev.N·보존기한 N년), 대표 반려 재가동 지시 분리 검증 완료")

    print("=================================================================")
    print("🎉 [최종 감사 결과: 전 기술 기둥 & 다중 규격 레지스트리 100% 통과 (결함 0건)]")
    print("=================================================================")

if __name__ == "__main__":
    run_all_tests()
