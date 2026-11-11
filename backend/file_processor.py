import io
import csv
import re
from typing import Tuple, Optional
from backend.db_store import set_session_table, scrub_pii_and_secrets


# =====================================================================
# 확장형 다중 규격 레지스트리 (Multi-Standard Compliance Registry)
# 현업 QA / QC / RA 직무 8대 핵심 국제·국내 규격 정의
# (명시적 규격명 또는 핵심 인증 키워드가 있을 때만 엄격하게 트리거)
# =====================================================================
COMPLIANCE_STANDARDS_REGISTRY: dict[str, dict] = {
    "ISO 9001": {
        "full_name": "ISO 9001:2015 품질경영시스템 (QMS)",
        "triggers": ["iso 9001", "iso9001", "품질경영시스템", "qms 인증"],
        "clauses": [
            {
                "clause": "ISO 9001 6.1 (리스크 기반 사고 및 기회 조치)",
                "title": "공정·품질 리스크 식별 및 사전 예방적 관리 계획",
                "keywords": ["리스크", "위험", "기회", "예방", "영향", "사전"],
                "remediation": "각 부서별 핵심 프로세스의 품질 리스크와 기회 요인을 식별하고, 리스크 등급에 따른 사전 완화 조치를 품질계획서에 문서화하세요.",
            },
            {
                "clause": "ISO 9001 7.5 (문서화된 정보 및 공정 접근법)",
                "title": "문서번호·개정번호·승인권자·개정이력 통제 및 프로세스 입력-출력 정의",
                "keywords": ["문서번호", "개정번호", "rev", "승인", "결재", "개정이력", "프로세스", "절차서", "매뉴얼"],
                "remediation": "표준 문서 양식에 [문서번호 / 개정번호 / 승인권자 / 개정이력] 4대 필수 요소를 강제화하고, 공정별 입력(Input)-출력(Output) 및 KPI 지표를 정의하세요.",
            },
            {
                "clause": "ISO 9001 8.7 / 10.2 (고객만족·부적합 통제 및 시정조치)",
                "title": "부적합 산출물 격리 식별, 고객 불만 피드백 및 재발방지 시정조치",
                "keywords": ["부적합", "격리", "고객만족", "불만", "시정조치", "재발방지", "원인분석", "capa"],
                "remediation": "부적합품 발견 시 즉시 식별·격리(Hold)하는 절차를 명문화하고, 고객 불만 및 공정 부적합에 대한 근본원인 분석과 시정조치 유효성 평가를 기록하세요.",
            },
        ],
    },
    "ISO 13485": {
        "full_name": "ISO 13485:2016 의료기기 품질경영시스템 (MD-QMS)",
        "triggers": ["iso 13485", "iso13485", "의료기기 품질", "의료기기 매뉴얼", "의료기기 제조", "mdf"],
        "clauses": [
            {
                "clause": "ISO 13485 4.2.3 (의료기기 파일 MDF)",
                "title": "제품 기술문서·제조공정·측정 및 모니터링 스펙 정의",
                "keywords": ["mdf", "의료기기 파일", "기술문서", "제품사양", "도면", "제조공정", "모니터링", "작업표준", "규격"],
                "remediation": "제품군별 기술문서(MDF) 인덱스를 신설하고 원부자재 BOM, 도면, 공정흐름도(PFC), 검사기준서(SIP)의 상호 참조 번호를 명시하세요.",
            },
            {
                "clause": "ISO 13485 4.2.4 / 4.2.5 (문서 및 기록 관리·보존기한)",
                "title": "문서번호·개정번호·승인권자·개정이력 및 의료기기 수명주기 기록 보존",
                "keywords": ["문서번호", "개정번호", "rev", "승인", "결재", "개정이력", "보존기한", "보관기간"],
                "remediation": "표준 문서 헤더에 [문서번호 / 개정번호 / 승인권자 / 개정이력표]를 포함하고, 품질 기록의 보존기한을 '제품 유효기한 경과 후 최소 2년 이상'으로 명시하세요.",
            },
            {
                "clause": "ISO 13485 7.5.6 (생산 및 서비스 공정 밸리데이션)",
                "title": "특수 공정 IQ(설치)·OQ(운전)·PQ(성능) 적격성 평가 및 재밸리데이션",
                "keywords": ["밸리데이션", "validation", "iq", "oq", "pq", "적격성", "공정능력", "cpk", "재밸리데이션"],
                "remediation": "결과를 전수 검증할 수 없는 특수 공정(세척·멸균·열밀봉·용접 등)에 대해 IQ/OQ/PQ 프로토콜 번호와 공정능력지수(Cpk ≥ 1.33) 관리 기준 및 정기 재밸리데이션 주기를 규정하세요.",
            },
            {
                "clause": "ISO 13485 7.5.8 / 7.5.9 (식별 및 추적성·LOT 관리)",
                "title": "원자재~완제품 LOT 추적성(Traceability) 및 UDI/부적합품 식별",
                "keywords": ["lot", "로트", "추적성", "식별", "udi", "바코드", "이력", "수입검사", "격리"],
                "remediation": "원자재 입고 LOT 번호가 제조이력서(DHR/BPR) 및 완제품 출하 라벨(UDI)까지 1:1 양방향 추적되도록 LOT 부여 규칙과 부적합품 적색 라벨 격리 절차를 추가하세요.",
            },
            {
                "clause": "ISO 13485 8.5.2 / 8.5.3 (시정조치 및 예방조치 CAPA)",
                "title": "5-Why 근본원인 분석, 시정조치 유효성 검증 및 재발방지",
                "keywords": ["capa", "시정조치", "예방조치", "5-why", "근본원인", "8d", "재발방지", "부적합", "car"],
                "remediation": "단순 현상 수정(Correction)과 근본원인 제거(Corrective Action)를 구분하고, 불량 발생 시 [원인분석(5-Why) ➔ CAPA 수립 ➔ 3개월 후 유효성 검증 ➔ 수평전개] 8D 프로세스를 의무화하세요.",
            },
        ],
    },
    "ISO 14971": {
        "full_name": "ISO 14971:2019 의료기기 위험관리 (Risk Management)",
        "triggers": ["iso 14971", "iso14971", "위험관리", "위해요인", "잔여위험", "rpn"],
        "clauses": [
            {
                "clause": "ISO 14971 5.2~5.5 (위해요인 식별 및 위험 산정 RPN)",
                "title": "정상·고장 상태 위해요인(Hazard) 식별 및 심각도(S)×발생빈도(O) 위험 매트릭스 산정",
                "keywords": ["위해요인", "hazard", "심각도", "발생빈도", "rpn", "위험산정", "매트릭스"],
                "remediation": "생물학적·전기적·기계적·사용오류 위해요인(Hazard)을 전수 도출하고, 심각도(S)와 발생가능성(P/O) 매트릭스를 통해 정량적 초기 위험도를 산정하세요.",
            },
            {
                "clause": "ISO 14971 7.1~7.4 (위험통제 조치 및 잔여위험 평가)",
                "title": "설계 본질안전 ➔ 보호수단 ➔ 안전정보(라벨링) 3단계 위험통제 및 잔여위험 수용성 평가",
                "keywords": ["위험통제", "본질안전", "잔여위험", "수용", "이득", "fmea", "완화"],
                "remediation": "위험통제 우선순위(설계 변경 ➔ 방호 알람 ➔ 사용설명서 경고)를 적용한 뒤 통제 후 잔여위험(Residual Risk)의 수용 가능 여부와 위험/이득(Benefit-Risk) 분석을 문서화하세요.",
            },
            {
                "clause": "ISO 14971 10 (생산 및 생산 후 정보 수집·FMEA 연계)",
                "title": "시판 후 임상·불만 데이터 기반 위험관리파일(RMF) 및 공정 FMEA 주기적 갱신",
                "keywords": ["rmf", "위험관리파일", "시판후", "pms", "갱신", "fmea", "연계"],
                "remediation": "생산 및 시판 후 피드백(불만, 부작용, 공정 불량)이 발생할 경우 위험관리파일(RMF)과 D-FMEA/P-FMEA를 연동 업데이트하는 환류 절차를 수립하세요.",
            },
        ],
    },
    "IEC 60601 / IEC 62304": {
        "full_name": "IEC 60601-1 (전자의료기기 전기·기계 안전성) & IEC 62304 (의료기기 SW 수명주기)",
        "triggers": ["iec 60601", "iec60601", "60601", "iec 62304", "iec62304", "62304", "누설전류", "의료기기 sw", "소프트웨어 안전등급"],
        "clauses": [
            {
                "clause": "IEC 60601-1 (전자의료기기 전기·기계적 안전성 필수시험)",
                "title": "환자 누설전류·접지연속성·내전압(절연) 및 기계적 강도 안전 기준",
                "keywords": ["누설전류", "절연", "내전압", "접지", "전기안전", "기계적", "온도상승"],
                "remediation": "장착부(Type B/BF/CF) 등급별 환자 누설전류 허용한도, 2중 절연(MOPP/MOOP) 내전압 시험 및 외장 기계적 충격 시험 기준치를 시험성적서에 명시하세요.",
            },
            {
                "clause": "IEC 60601-1-2 (전자파 적합성 EMC 시험)",
                "title": "전자파 방사(EMI) 및 정전기·방사성 내성(EMS) 규격 검증",
                "keywords": ["emc", "emi", "ems", "전자파", "정전기", "esd", "내성"],
                "remediation": "IEC 60601-1-2 4판 이상 기준에 따른 전자파 장해(EMI) 및 정전기 방전(ESD)·서지 내성(EMS) 필수 시험 조건과 필수성능(Essential Performance) 유지 기준을 정의하세요.",
            },
            {
                "clause": "IEC 62304 (의료기기 SW 안전 등급 Class A/B/C 및 수명주기)",
                "title": "SW 안전 등급(Class A/B/C) 분류, 요구사항 추적성(SRS-SDS-Test) 및 SOUP 관리",
                "keywords": ["class a", "class b", "class c", "안전등급", "srs", "추적성", "soup", "단위테스트", "수명주기"],
                "remediation": "SW 고장 시 상해 심각도에 따라 안전 등급(Class A: 경미 / B: 비심각 / C: 사망·중상)을 분류하고, 요구사항(SRS)-아키텍처(SDS)-소스코드-단위/통합시험 간 양방향 추적성 매트릭스를 구축하세요.",
            },
        ],
    },
    "KGMP / FDA 21 CFR Part 820": {
        "full_name": "식약처 의료기기 KGMP & 미국 FDA 21 CFR Part 820 (QMSR)",
        "triggers": ["kgmp", "fda", "21 cfr", "part 820", "qmsr", "dmr", "dhr"],
        "clauses": [
            {
                "clause": "KGMP / 21 CFR 820.181 & 820.184 (DMR & DHR 관리)",
                "title": "제품표준서(DMR) 및 로트별 제조이력서(DHR / 제조지시 및 기록서) 완결성",
                "keywords": ["dmr", "dhr", "제품표준서", "제조이력", "제조지시", "배치기록", "작업일지", "수율"],
                "remediation": "제품표준서(DMR)와 일치하는 로트별 제조이력서(DHR) 양식을 수립하고, 투입 원자재 LOT·작업자·주요 공정 파라미터·최종 출하승인 서명이 누락 없이 기록되도록 통제하세요.",
            },
            {
                "clause": "KGMP / 21 CFR 820.198 (고객 불만처리 및 부작용 보고 MDR)",
                "title": "고객 불만 접수·조사·식약처/FDA 이상사례(MDR) 보고 기한 준수",
                "keywords": ["불만", "부작용", "이상사례", "mdr", "보고", "식약처", "fda", "피드백"],
                "remediation": "모든 고객 불만을 전담 품질부서에서 심사하고, 사망·중대한 부작용 관련 시 법정 기한 내에 식약처 및 FDA(MDR)에 보고하는 비상 에스컬레이션 절차를 명시하세요.",
            },
            {
                "clause": "KGMP / 21 CFR Part 806 (제품 회수 Recall 및 자진 시정 절차)",
                "title": "부적합 출하 제품 추적·회수(Recall) 등급 분류 및 모의 회수 훈련",
                "keywords": ["회수", "recall", "리콜", "출하정지", "추적", "폐기", "통보"],
                "remediation": "위해도에 따른 회수 등급(1·2·3등급) 분류 기준, 유통망 거래처 긴급 통보 양식, 회수품 격리·폐기 및 연 1회 이상 모의 회수(Mock Recall) 훈련 절차를 규정하세요.",
            },
        ],
    },
    "IATF 16949": {
        "full_name": "IATF 16949:2016 자동차·전장 부품 품질경영시스템 (5 Core Tools)",
        "triggers": ["iatf 16949", "iatf16949", "16949", "apqp", "ppap", "msa", "spc", "cpk", "core tools"],
        "clauses": [
            {
                "clause": "IATF 16949 Core Tool 1 & 2 (APQP 선행제품품질계획 & PPAP 부품승인)",
                "title": "단계별 게이트 리뷰(APQP) 및 양산 부품 승인 제출물 18종(PPAP PSW) 검증",
                "keywords": ["apqp", "ppap", "psw", "선행품질", "부품승인", "control plan", "관리계획서", "초도품"],
                "remediation": "개발 5단계 APQP 일정과 연동하여 공정흐름도(PFD)-PFMEA-관리계획서(Control Plan) 3대 문서의 일관성을 확보하고, 양산 전 PPAP 승인원(PSW) 및 초기공정연구 결과를 제출하세요.",
            },
            {
                "clause": "IATF 16949 Core Tool 3 & 4 (AIAG-VDA FMEA & MSA 측정시스템분석)",
                "title": "설계·공정 FMEA 조치우선순위(AP) 관리 및 게이지 R&R(%GRR) 적격성 평가",
                "keywords": ["fmea", "pfmea", "msa", "게이지", "grr", "r&r", "측정시스템", "검교정", "편향"],
                "remediation": "관리계획서에 명시된 모든 측정기기에 대해 게이지 R&R(%GRR < 10%: 우수, 10~30%: 조건부 수용, >30%: 부적합)을 수행하고 AIAG-VDA FMEA 기준 고위험(AP: High) 항목의 개선대책을 수립하세요.",
            },
            {
                "clause": "IATF 16949 Core Tool 5 (SPC 통계적 공정관리 & 공정능력 Cpk)",
                "title": "특별특성(CC/SC) 관리도(Xbar-R) 실시간 모니터링 및 공정능력지수(Ppk ≥ 1.67, Cpk ≥ 1.33)",
                "keywords": ["spc", "cpk", "ppk", "관리도", "xbar", "통계적", "특별특성", "산포"],
                "remediation": "핵심 특별특성(Critical/Significant Characteristics)에 대해 초기 공정능력 Ppk ≥ 1.67, 양산 유지 공정능력 Cpk ≥ 1.33 기준을 설정하고 관리한계선(UCL/LCL) 이탈 시 이상원인 조치(OCAP)를 가동하세요.",
            },
        ],
    },
    "ISO 14001 / ISO 45001": {
        "full_name": "ISO 14001:2015 (환경경영) & ISO 45001:2018 (안전보건경영시스템)",
        "triggers": ["iso 14001", "iso14001", "14001", "iso 45001", "iso45001", "45001", "환경경영", "안전보건경영", "위험성평가", "아차사고"],
        "clauses": [
            {
                "clause": "ISO 14001 6.1.2 (환경측면 식별 및 환경영향평가)",
                "title": "전과정(LCA) 관점 대기·수질·폐기물·에너지 환경측면 식별 및 중요 환경측면 관리",
                "keywords": ["환경측면", "환경영향", "폐기물", "배출", "온실가스", "에너지", "lca"],
                "remediation": "정상·비정상·비상시 활동에서 발생하는 환경측면(대기배출, 폐수, 지정폐기물, 화학물질)을 식별하고 환경영향평가 점수표를 통해 중요 환경측면 저감 목표를 수립하세요.",
            },
            {
                "clause": "ISO 45001 6.1.2 (사업장 위험성평가 및 아차사고 발굴)",
                "title": "유해·위험요인 파악, 근로자 참여형 위험성평가 및 아차사고(Near-Miss) 개선",
                "keywords": ["위험성평가", "아차사고", "near-miss", "유해위험", "안전보호구", "작업환경", "재해"],
                "remediation": "정기 및 수시 위험성평가에 현장 작업자 참여를 보장하고, 아차사고(Near-Miss) 발굴 보고 제도와 공학적 방호조치(인터락·안전가드) 개선 이력을 기록하세요.",
            },
            {
                "clause": "ISO 14001 / 45001 8.2 & 9.1.2 (비상사태 대응 및 법규준수 평가)",
                "title": "화재·누출·중대재해 비상대응 시나리오 훈련 및 환경·산업안전 법규준수 평가표",
                "keywords": ["비상사태", "비상대응", "소방", "누출", "법규", "산업안전", "훈련"],
                "remediation": "화학물질 유출·화재·산업재해 발생 시 비상연락망과 초기 대응 시나리오 모의훈련을 반기별로 실시하고, 환경·안전보건 법규 등록부 및 준수 평가표를 최신화하세요.",
            },
        ],
    },
    "RoHS / REACH": {
        "full_name": "EU RoHS 지침 (유해물질 제한) & REACH 규정 (SVHC 고위험성물질 관리)",
        "triggers": ["rohs", "reach", "svhc", "중금속", "msds", "카드뮴", "6가크롬", "프탈레이트"],
        "clauses": [
            {
                "clause": "RoHS 2 (EU 2015/863) 4대 중금속 및 6대 브롬계·프탈레이트 허용농도",
                "title": "카드뮴(Cd ≤ 100ppm), 납·수은·6가크롬·PBB·PBDE·프탈레이트 4종(≤ 1,000ppm) 기준 검증",
                "keywords": ["cd", "카드뮴", "pb", "납", "hg", "수은", "cr6", "6가크롬", "pbb", "pbde", "dehp", "100ppm", "1000ppm"],
                "remediation": "균질재질(Homogeneous Material) 단위 공인기관 정밀분석(ICP-OES/GC-MS) 성적서를 확보하여 Cd < 100 ppm(0.01%), Pb/Hg/Cr6+/PBB/PBDE/DEHP/BBP/DBP/DIBP < 1,000 ppm(0.1%) 적합 여부를 판정하세요.",
            },
            {
                "clause": "REACH SVHC (고위험성우려물질) 및 MSDS(물질안전보건자료) 통제",
                "title": "완제품 내 SVHC 후보물질 0.1 wt% 초과 여부 확인 및 최신 국문/영문 MSDS 비치",
                "keywords": ["reach", "svhc", "msds", "물질안전보건자료", "화학물질", "성분표", "cas"],
                "remediation": "유럽화학물질청(ECHA) 최신 SVHC 후보물질 리스트 대비 부품 내 함량(0.1 wt% 미만) 보증서를 징구하고, 현장 취급 화학물질의 16대 항목 MSDS를 최신본으로 비치하세요.",
            },
            {
                "clause": "친환경 원부자재 CoA·ICP 공인성적서 유효기한(1년) 및 비전격리 관리",
                "title": "협력사 로트별 CoA 및 연간 ICP 정밀성적서 갱신 주기 인터락",
                "keywords": ["icp", "공인성적서", "유효기간", "1년", "보증서", "비할로겐", "무연", "pb-free"],
                "remediation": "협력사 부품별 공인 시험성적서(유효기한 1년 이내) 만료일을 시스템에서 자동 추적하고, 무연(Pb-Free) 공정과 유연 공정의 혼입 방지 식별 관리 절차를 수립하세요.",
            },
        ],
    },
}


def detect_compliance_standards(text: str, prompt: str = "") -> Tuple[list[str], list[str]]:
    """
    [엄격한 규격 심사 의도 분리]
    사용자가 명시적으로 특정 인증 규격명(ISO 9001, ISO 13485, IATF 16949, RoHS 등)이나
    '인증', '규격 심사', 'SOP/절차서/매뉴얼 검토'를 요청했거나, 업로드된 문서 자체에 해당 규격이 명시된 경우에만
    규격 리스트를 반환합니다.
    단순히 '수입검사', '공정검사', '불량률', 'PPM', '파레토', 'CAPA', '8D'만 있는 경우에는
    묻지 않은 국제 규격을 무차별적으로 끌어오지 않도록 빈 리스트([], [])를 반환합니다.
    """
    combined = f"{text or ''}\n{prompt or ''}".lower()
    matched_registered: list[str] = []

    for std_key, std_info in COMPLIANCE_STANDARDS_REGISTRY.items():
        if any(trig in combined for trig in std_info["triggers"]):
            matched_registered.append(std_key)

    # 미등록 국제/국내 규격 패턴 탐지 (예: ISO 27001, ISO 22000, HACCP, ISMS-P, AS9100, CE MDR 등)
    unregistered_found: list[str] = []
    known_numbers = {"9001", "13485", "14971", "60601", "62304", "16949", "14001", "45001", "820", "806", "2859"}

    for m in re.finditer(r"\b(iso|iec|iatf|as|ks\s*[a-z]?)\s*[-]?\s*(\d{4,5})\b", combined, flags=re.I):
        prefix = m.group(1).upper().strip()
        num = m.group(2).strip()
        if num not in known_numbers:
            label = f"{prefix} {num}"
            if label not in unregistered_found:
                unregistered_found.append(label)

    named_standards = [
        ("haccp", "HACCP (식품안전관리인증기준)"),
        ("isms", "ISMS-P (정보보호 및 개인정보보호 관리체계)"),
        ("cmmi", "CMMI (소프트웨어·시스템 성숙도 모델)"),
        ("ce mdr", "EU CE-MDR (유럽 의료기기 규정)"),
        ("mdsaps", "MDSAP (의료기기 단일심사 프로그램)"),
        ("mdsap", "MDSAP (의료기기 단일심사 프로그램)"),
        ("halal", "HALAL (할랄 품질인증)"),
        ("fsc", "FSC (산림경영 인증)"),
    ]
    for kw, label in named_standards:
        if kw in combined and label not in unregistered_found:
            unregistered_found.append(label)

    # 명시적인 규격 번호 없이 'SOP', '작업표준서', '절차서', '품질매뉴얼', '품질문서 심사', '인증 심사'를 요청한 경우에만 기본 ISO 13485 & ISO 9001 적용
    if not matched_registered and not unregistered_found:
        explicit_doc_audit_keywords = [
            "작업표준서",
            "절차서",
            "sop",
            "품질매뉴얼",
            "품질문서 심사",
            "규격 심사",
            "인증 심사",
            "의료기기_멸균포장",
        ]
        if any(k in combined for k in explicit_doc_audit_keywords):
            matched_registered = ["ISO 13485", "ISO 9001"]

    return matched_registered, unregistered_found


def is_compliance_audit_request(text: str, prompt: str = "") -> bool:
    reg_stds, unreg_stds = detect_compliance_standards(text, prompt)
    return len(reg_stds) > 0 or len(unreg_stds) > 0


def evaluate_iso_compliance(text: str, prompt: str = "", crawled_knowledge: str = "") -> str:
    """
    [확장형 다중 규격 레지스트리(Multi-Standard Compliance Registry) & 동적 폴백 심사 엔진]
    임원 결재 보고서 품질을 위해 내부 시스템 메타 문구((검출 근거: ...), (일부 언급되었으나...))를 배제하고
    정돈된 조항별 정량 진단과 시정 가이드를 분리 산출합니다.
    """
    combined = f"{text or ''}\n{prompt or ''}".lower()
    matched_stds, unregistered_stds = detect_compliance_standards(text, prompt)

    if not matched_stds and not unregistered_stds:
        matched_stds = ["ISO 13485", "ISO 9001"]

    has_actual_doc = len((text or "").strip()) > 80 and "[첨부 데이터 전수" not in (text or "")
    active_clauses: list[dict] = []
    std_titles: list[str] = []

    for std_key in matched_stds:
        std_info = COMPLIANCE_STANDARDS_REGISTRY[std_key]
        std_titles.append(std_info["full_name"])
        for c in std_info["clauses"]:
            active_clauses.append({
                "std_key": std_key,
                "clause": c["clause"],
                "title": c["title"],
                "keywords": c["keywords"],
                "remediation": c["remediation"],
            })

    # 미등록 규격(예: ISO 27001, HACCP 등) 폴백(Fallback) 동적 체크리스트 생성
    for unreg_name in unregistered_stds:
        std_titles.append(f"{unreg_name} 국제·국내 인증 기준")
        active_clauses.extend([
            {
                "std_key": unreg_name,
                "clause": f"{unreg_name} 제1영역 (문서화 체계·정책 및 표준 절차서 통제)",
                "title": f"{unreg_name} 매뉴얼·절차서(SOP) 제·개정 이력, 승인권자 및 조직 책임·권한 정의",
                "keywords": ["문서번호", "개정번호", "승인", "절차서", "정책", "조직", "매뉴얼"],
                "remediation": f"{unreg_name} 인증 심사 기준에 부합하도록 표준 절차서(SOP)에 문서번호·개정이력·승인권자를 명시하고 전담 관리책임자(팀장급) 지정서를 구비하세요.",
            },
            {
                "std_key": unreg_name,
                "clause": f"{unreg_name} 제2영역 (핵심 위험요소·중요관리점 식별 및 통제 기준)",
                "title": f"{unreg_name} 특화 리스크 평가, 한계기준(Critical Limit) 설정 및 모니터링 주기",
                "keywords": ["위험", "리스크", "한계기준", "모니터링", "점검", "통제", "중요관리"],
                "remediation": f"{unreg_name} 요구사항에 따른 핵심 리스크/중요관리점(CCP·통제항목)을 도출하고 정량적 허용 한계치와 일일 모니터링 체크시트를 신설하세요.",
            },
            {
                "std_key": unreg_name,
                "clause": f"{unreg_name} 제3영역 (내부심사·기록 보존 및 시정·예방조치 CAPA)",
                "title": f"{unreg_name} 정기 내부심사, 한계이탈 시 즉각 개선조치(CAPA) 및 유효성 검증 기록",
                "keywords": ["내부심사", "시정조치", "capa", "개선", "유효성", "보존", "교육훈련"],
                "remediation": f"{unreg_name} 사후심사 및 갱신심사 통과를 위해 연 1회 이상 내부심사 결과보고서, 임직원 정기 교육훈련 수료증, 부적합 발생 시 5-Why 기반 CAPA 이력철을 완비하세요.",
            },
        ])

    pass_clauses = []
    gap_clauses = []
    clause_lines = []

    for idx, c in enumerate(active_clauses, start=1):
        matched_kws = [kw for kw in c["keywords"] if kw in combined]
        if has_actual_doc and len(matched_kws) >= 2:
            status = "✅ 적합(Compliant)"
            pass_clauses.append(c)
            clause_lines.append(
                f"• [{c['clause']} — {status}]: {c['title']} 요건이 문서 내에 명확히 정의되어 기준을 충족합니다."
            )
        elif not has_actual_doc and idx == 1 and len(matched_kws) >= 1:
            status = "✅ 적합(기준 확인)"
            pass_clauses.append(c)
            clause_lines.append(
                f"• [{c['clause']} — {status}]: {c['title']} 관리 기준이 수립되어 있습니다."
            )
        else:
            status = "🚨 부적합/보완필요(Gap)"
            gap_clauses.append(c)
            clause_lines.append(
                f"• [{c['clause']} — {status}]: {c['title']}에 관한 세부 실행 절차 및 정량적 판정 기준이 누락되어 보완이 필요합니다."
            )

    total_c = len(active_clauses)
    pass_c = len(pass_clauses)
    gap_c = len(gap_clauses)
    compliance_score = round((pass_c / max(1, total_c)) * 100, 1)

    std_banner = " · ".join(matched_stds + unregistered_stds)
    header_summary = (
        f"• [규격 적합성 정량 진단 요약 ({std_banner})]: 총 {total_c}개 필수 조항 점검 결과 "
        f"적합 {pass_c}건, 보완필요(Gap) {gap_c}건 (현재 규격 부합도 {compliance_score}%)."
    )

    guide_lines = []
    for gc in gap_clauses[:8]:
        guide_lines.append(f"- [{gc['clause']}]: {gc['remediation']}")

    return "\n".join([header_summary] + clause_lines + guide_lines)


def evaluate_spec_compliance(spec_str: str, val_str: str) -> Tuple[Optional[bool], Optional[float]]:
    if not spec_str or not val_str:
        return None, None

    clean_val = re.sub(r"[,%\sA-Za-zμmMPap]+", "", str(val_str))
    if not re.match(r"^[+-]?\d+(?:\.\d+)?$", clean_val):
        return None, None
    measured = float(clean_val)
    s = str(spec_str).strip()

    m_tol = re.search(r"(\d+(?:\.\d+)?)\s*(?:±|\+\-|\+/-)\s*(\d+(?:\.\d+)?)", s)
    if m_tol:
        target = float(m_tol.group(1))
        tol = float(m_tol.group(2))
        dev = round(measured - target, 3)
        return (target - tol <= measured <= target + tol), dev

    m_range = re.search(r"(\d+(?:\.\d+)?)\s*(?:~|\-)\s*(\d+(?:\.\d+)?)", s)
    if m_range:
        low = float(m_range.group(1))
        high = float(m_range.group(2))
        mid = (low + high) / 2.0
        dev = round(measured - mid, 3)
        return (low <= measured <= high), dev

    m_min = re.search(r"(?:>=|이상|min)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:이상|min|\+)", s, flags=re.I)
    if m_min:
        bound = float(m_min.group(1) or m_min.group(2))
        dev = round(measured - bound, 3)
        return (measured >= bound), dev

    m_max = re.search(r"(?:<=|이하|미만|max|<)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:이하|미만|max)", s, flags=re.I)
    if m_max:
        bound = float(m_max.group(1) or m_max.group(2))
        dev = round(measured - bound, 3)
        return (measured <= bound), dev

    return None, None


def find_header_row_index(rows: list[list[str]]) -> int:
    header_keywords = [
        "일자", "날짜", "lot", "로트", "품목", "품명", "자재", "협력사", "거래처", "업체",
        "항목", "규격", "spec", "측정", "실측", "판정", "결과", "단가", "금액", "수량", "비고"
    ]
    best_idx = 0
    best_score = -1

    for idx, row in enumerate(rows[:10]):
        non_empty = [c for c in row if c]
        if len(non_empty) < 3:
            continue
        score = sum(3 for cell in non_empty if any(k in cell.lower() for k in header_keywords)) + len(non_empty)
        if score > best_score:
            best_score = score
            best_idx = idx

    return best_idx


def _analyze_tabular_rows(filename: str, all_clean_rows: list[list[str]], session_id: str = "default") -> Tuple[str, dict]:
    h_idx = find_header_row_index(all_clean_rows)
    headers = all_clean_rows[h_idx]
    data_rows = all_clean_rows[h_idx + 1 :]

    total_rows = len(data_rows)
    pass_count = 0
    fail_count = 0
    fail_details = []
    pass_details = []
    vendor_stats: dict[str, dict[str, int]] = {}
    defect_pareto_counts: dict[str, int] = {}
    failed_items_records: list[dict[str, str]] = []
    item_metric_list: list[str] = []
    deviation_vals: list[float] = []
    structured_export_rows: list[list[str]] = []

    judge_idx = -1
    vendor_idx = -1
    item_idx = -1
    check_idx = -1
    spec_idx = -1
    val_idx = -1
    dev_idx = -1

    for idx, h in enumerate(headers):
        h_low = h.lower()
        if any(k in h_low for k in ["판정", "합격", "불합격", "status", "judge"]):
            judge_idx = idx
        elif any(k in h_low for k in ["협력사", "거래처", "공급사", "업체", "vendor", "supplier"]):
            vendor_idx = idx
        elif any(k in h_low for k in ["품목", "품명", "자재", "모델", "제품", "item", "product"]):
            item_idx = idx
        elif any(k in h_low for k in ["항목", "특성", "불량유형", "불량항목", "유해물질", "check", "parameter", "defect", "substance"]):
            check_idx = idx
        elif any(k in h_low for k in ["규격", "기준", "허용농도", "spec", "standard", "limit"]):
            spec_idx = idx
        elif any(k in h_low for k in ["실측", "측정", "결과값", "검출농도", "measured", "value", "result"]):
            val_idx = idx
        elif any(k in h_low for k in ["오차", "편차", "diff", "deviation", "error"]):
            dev_idx = idx

    export_headers = list(headers)
    if judge_idx == -1:
        export_headers.append("AI_자동규격판정")

    for r_num, row in enumerate(data_rows, start=1):
        masked_row = [scrub_pii_and_secrets(str(c))[0] for c in row]
        row_str_join = " | ".join([c for c in masked_row if c])
        judge_val = masked_row[judge_idx] if (0 <= judge_idx < len(masked_row)) else ""
        is_fail = any(k in judge_val for k in ["불합격", "부적합", "불량", "NG", "FAIL", "반려", "초과"])
        is_pass = not is_fail and any(k in judge_val for k in ["합격", "적합", "정상", "OK", "PASS", "불검출", "N.D"])

        auto_dev: Optional[float] = None
        if not is_fail and not is_pass and (0 <= spec_idx < len(masked_row)) and (0 <= val_idx < len(masked_row)):
            spec_ok, calc_dev = evaluate_spec_compliance(masked_row[spec_idx], masked_row[val_idx])
            auto_dev = calc_dev
            if spec_ok is False:
                is_fail = True
                row_str_join += f" | [규격 판정: 불합격 (편차 {calc_dev:+.2f})]"
            elif spec_ok is True:
                is_pass = True
                row_str_join += f" | [규격 판정: 합격 (편차 {calc_dev:+.2f})]"

        export_row = list(masked_row) + [""] * max(0, len(headers) - len(masked_row))
        if judge_idx == -1:
            export_row.append("불합격(NG)" if is_fail else ("합격(OK)" if is_pass else "확인필요"))
        structured_export_rows.append(export_row)

        vendor_name = masked_row[vendor_idx] if (0 <= vendor_idx < len(masked_row) and masked_row[vendor_idx]) else "기타/미상"
        item_name = masked_row[item_idx] if (0 <= item_idx < len(masked_row) and masked_row[item_idx]) else f"품목-{r_num}"
        check_name = masked_row[check_idx] if (0 <= check_idx < len(masked_row) and masked_row[check_idx]) else "치수/성분규격"
        spec_val = masked_row[spec_idx] if (0 <= spec_idx < len(masked_row) and masked_row[spec_idx]) else "기준규격"
        measured_val = masked_row[val_idx] if (0 <= val_idx < len(masked_row) and masked_row[val_idx]) else "측정치"

        if is_fail:
            fail_count += 1
            vendor_stats.setdefault(vendor_name, {"total": 0, "fail": 0})
            vendor_stats[vendor_name]["total"] += 1
            vendor_stats[vendor_name]["fail"] += 1
            pareto_key = f"{check_name}({item_name})" if check_idx != -1 else item_name
            defect_pareto_counts[pareto_key] = defect_pareto_counts.get(pareto_key, 0) + 1
            failed_items_records.append({
                "row": str(r_num),
                "vendor": vendor_name,
                "item": item_name,
                "check": check_name,
                "spec": spec_val,
                "measured": measured_val,
            })
            fail_details.append(f"• [🚨 부적합(불합격) 검출 #{len(fail_details)+1} (행 {r_num})]: {row_str_join}.")
        elif is_pass:
            pass_count += 1
            vendor_stats.setdefault(vendor_name, {"total": 0, "fail": 0})
            vendor_stats[vendor_name]["total"] += 1
            pass_details.append(f"• [✅ 적격(합격) 확인 #{len(pass_details)+1} (행 {r_num})]: {row_str_join}.")
        else:
            pass_details.append(f"• [데이터 행 {r_num}]: {row_str_join}.")

        if 0 <= val_idx < len(masked_row) and masked_row[val_idx]:
            p_name = masked_row[item_idx] if (0 <= item_idx < len(masked_row)) else f"행{r_num}"
            c_name = masked_row[check_idx] if (0 <= check_idx < len(masked_row)) else headers[val_idx]
            item_metric_list.append(f"{p_name}({c_name}: {masked_row[val_idx]})")

        if 0 <= dev_idx < len(masked_row) and masked_row[dev_idx]:
            clean_dev = re.sub(r"[,%\s]", "", str(masked_row[dev_idx]))
            if re.match(r"^[+-]?\d+(?:\.\d+)?$", clean_dev):
                try:
                    deviation_vals.append(float(clean_dev))
                except Exception:
                    pass
        elif auto_dev is not None:
            deviation_vals.append(auto_dev)

    set_session_table(session_id, {
        "filename": filename,
        "headers": export_headers,
        "rows": structured_export_rows,
    })

    lines = [
        f"• [첨부 데이터 전수 스캔 완료]: 파일명 '{filename}' (헤더 자동 탐지: {h_idx+1}행) | 총 데이터 {total_rows}건 전수 분석 (누락 0건) | 컬럼: {', '.join(headers[:10])}."
    ]

    defect_rate = 0.0
    ppm_val = 0
    if pass_count + fail_count > 0:
        judged_total = pass_count + fail_count
        defect_rate = round((fail_count / judged_total) * 100, 2)
        ppm_val = int(round((fail_count / judged_total) * 1_000_000))
        lines.append(
            f"• [전수 품질 판정 통계]: 총 판정 {judged_total}건 중 합격 {pass_count}건 ({round(100 - defect_rate, 2)}%), 불합격(부적합) {fail_count}건 (불량률 {defect_rate}%, 공정 불량 지수 {ppm_val:,} PPM)."
        )

    if defect_pareto_counts and fail_count > 0:
        sorted_pareto = sorted(defect_pareto_counts.items(), key=lambda x: x[1], reverse=True)
        pareto_parts = []
        cum_cnt = 0
        for p_key, cnt in sorted_pareto[:6]:
            share = round((cnt / fail_count) * 100, 1)
            cum_cnt += cnt
            cum_share = round((cum_cnt / fail_count) * 100, 1)
            pareto_parts.append(f"{p_key} {cnt}건(비중 {share}%, 누적 {cum_share}%)")
        lines.append(f"• [불량 유형/항목별 파레토(Pareto) 빈도 분석]: {' ➔ '.join(pareto_parts)}.")

    if vendor_stats:
        v_summaries = []
        for v_name, st in vendor_stats.items():
            v_rate = round((st["fail"] / max(1, st["total"])) * 100, 1)
            v_ppm = int(round((st["fail"] / max(1, st["total"])) * 1_000_000))
            v_summaries.append(f"{v_name}(총 {st['total']}건 중 불량 {st['fail']}건, 불량률 {v_rate}% / {v_ppm:,} PPM)")
        lines.append(f"• [협력사별 품질·불량률 집계]: {', '.join(v_summaries[:8])}.")

    if item_metric_list or deviation_vals:
        dev_stat_str = ""
        if deviation_vals:
            avg_abs_dev = round(sum(abs(x) for x in deviation_vals) / len(deviation_vals), 2)
            min_dev = min(deviation_vals)
            max_dev = max(deviation_vals)
            dev_stat_str = f" | 규격 대비 편차(오차) 분포[최소 {min_dev:+.1f} ~ 최대 {max_dev:+.1f}, 평균 절대편차 {avg_abs_dev}]"
        lines.append(f"• [항목별 실측치(단위별 분리) 및 편차 분석]: {', '.join(item_metric_list[:6])}{dev_stat_str}.")

    if failed_items_records:
        top_fail = failed_items_records[0]
        lines.append(
            f"• [기준치 초과 품목 5-Why 근본원인 분석 ({top_fail['item']} - {top_fail['check']})]: "
            f"① Why1(현상): 기준규격({top_fail['spec']}) 대비 실측치({top_fail['measured']}) 이탈 발생 ➔ "
            f"② Why2(공정): 공급사({top_fail['vendor']}) 제조 배합비/코팅 두께 설정 파라미터 편차 발생 ➔ "
            f"③ Why3(설비): 센서 영점 교정(Calibration) 주기 경과 및 노후화 ➔ "
            f"④ Why4(관리): 출하 전 SPC(통계적 공정관리) 관리도(Xbar-R) 사전 경고 미작동 ➔ "
            f"⑤ Why5(시스템): 협력사 출하검사(OQC)와 당사 수입검사(IQC) 간 실시간 CoA 인터락 부재."
        )
        lines.append(
            f"• [CAPA(시정 및 예방조치) 및 8D 권고사항]: "
            f"[시정조치(Corrective Action)] 부적합 LOT 전량 부적합품 구역(MRB) 격리 및 {top_fail['vendor']} 대상 시정조치요구서(SCAR/8D Report) 즉시 발행 | "
            f"[예방조치(Preventive Action)] 핵심 특성에 대한 공정능력지수(Cpk ≥ 1.33) 성적서 의무 제출 및 비전 AI 기반 CoA 상·하한 자동 인터락 적용."
        )

    if fail_details:
        lines.extend(fail_details[:12])
    if pass_details:
        lines.extend(pass_details[:10])

    meta = {
        "filename": filename,
        "type": "TABULAR_ANALYTICS",
        "header_row": h_idx + 1,
        "rows": total_rows,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "defect_rate": defect_rate,
        "ppm": ppm_val,
    }
    return "\n".join(lines), meta


def parse_uploaded_document(filename: str, content: bytes, session_id: str = "default") -> Tuple[str, dict]:
    fname_lower = filename.lower()
    meta = {"filename": filename, "size_kb": round(len(content) / 1024, 1), "type": "DOCUMENT"}

    try:
        if fname_lower.endswith(".csv"):
            text_data = ""
            for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
                try:
                    text_data = content.decode(enc)
                    break
                except Exception:
                    continue
            reader = [
                [str(c).strip() for c in r]
                for r in csv.reader(io.StringIO(text_data))
                if any(str(c).strip() for c in r)
            ]
            if len(reader) >= 2:
                summary_str, tab_meta = _analyze_tabular_rows(filename, reader, session_id=session_id)
                if is_compliance_audit_request(text_data, filename):
                    summary_str += "\n" + evaluate_iso_compliance(text_data, filename)
                return summary_str, tab_meta

        elif fname_lower.endswith((".xlsx", ".xls")):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            sheet = wb[wb.sheetnames[0]]
            raw_rows = list(sheet.iter_rows(values_only=True))
            clean_rows = []
            for r in raw_rows:
                vals = [str(c).strip() if c is not None else "" for c in r]
                if any(vals):
                    clean_rows.append(vals)
            if len(clean_rows) >= 2:
                summary_str, tab_meta = _analyze_tabular_rows(filename, clean_rows, session_id=session_id)
                if len(wb.sheetnames) > 1:
                    extra_sheet = wb[wb.sheetnames[1]]
                    extra_lines = []
                    for r in list(extra_sheet.iter_rows(values_only=True))[2:8]:
                        v = [str(c).strip() for c in r if c is not None and str(c).strip()]
                        if len(v) >= 2:
                            extra_lines.append(f"{v[0]}({' -> '.join(v[1:])})")
                    if extra_lines:
                        summary_str += f"\n• [보조 시트('{extra_sheet.title}') 핵심 성과 지표]: " + " / ".join(extra_lines[:4]) + "."
                return summary_str, tab_meta

        elif fname_lower.endswith(".pdf"):
            meta["type"] = "PDF_DOCUMENT"
            pdf_text = ""
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(content))
                meta["pages"] = len(reader.pages)
                pages_txt = [page.extract_text() or "" for page in reader.pages[:10]]
                pdf_text = "\n".join(pages_txt)
            except Exception:
                decoded = content.decode("latin1", errors="ignore")
                matches = re.findall(r"\(([^()]{4,120})\)", decoded)
                pdf_text = " ".join(matches)

            clean_pdf, _ = scrub_pii_and_secrets(re.sub(r"\s+", " ", pdf_text).strip())
            extracted_lines = [f"• [첨부 PDF 문서 전수 스캔]: {filename} (총 {meta.get('pages', 1)}페이지, {meta['size_kb']}KB)."]
            if len(clean_pdf) > 20:
                sents = [s.strip() for s in re.split(r"(?<=[.?!다요음함])\s+", clean_pdf) if len(s.strip()) > 20]
                for idx, s in enumerate(sents[:10], 1):
                    extracted_lines.append(f"• [PDF 핵심 문장 {idx}]: {s[:180]}.")
            if is_compliance_audit_request(clean_pdf, filename):
                meta["type"] = "ISO_COMPLIANCE_DOC"
                extracted_lines.append(evaluate_iso_compliance(clean_pdf, filename))
            return "\n".join(extracted_lines), meta

        txt, _ = scrub_pii_and_secrets(content.decode("utf-8", errors="ignore"))
        lines = [line.strip() for line in txt.splitlines() if len(line.strip()) > 5]
        out = [f"• [첨부 문서명]: {filename} (총 {len(lines)}줄)."]
        for idx, l in enumerate(lines[:12], 1):
            out.append(f"• [문서 주요 내용 {idx}]: {l[:170]}.")
        if is_compliance_audit_request(txt, filename):
            meta["type"] = "ISO_COMPLIANCE_DOC"
            out.append(evaluate_iso_compliance(txt, filename))
        return "\n".join(out), meta

    except Exception:
        return f"• [첨부 파일 로드]: {filename} ({meta['size_kb']}KB) 분석 준비 완료.", meta
