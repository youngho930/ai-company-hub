import io
import csv
import re
import math
import statistics
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
                "title": "공정·품질 리스크 식별 및 사전 예방적 관리 계획 누락",
                "keywords": ["리스크", "위험", "기회", "예방", "영향", "사전"],
                "remediation": "각 부서별 핵심 프로세스의 품질 리스크와 기회 요인을 식별하고, 리스크 등급에 따른 사전 완화 조치를 품질계획서에 문서화하세요.",
                "template_snippet": "본 공정 수행 전 품질보증팀장은 연 1회 이상 공정 리스크 및 기회 평가표(FMEA 연계)를 작성하며, 중점 관리 항목은 초기 공정능력 Ppk >= 1.67, 양산 Cpk >= 1.33 이상을 유지하도록 사전 예방 관리한다.",
            },
            {
                "clause": "ISO 9001 7.5 (문서화된 정보 및 공정 접근법)",
                "title": "문서번호·개정번호·승인권자·개정이력 4대 통제 요소 및 프로세스 입출력 정의 미비",
                "keywords": ["문서번호", "개정번호", "rev", "승인", "결재", "개정이력", "프로세스", "절차서", "매뉴얼"],
                "remediation": "표준 문서 양식에 [문서번호 / 개정번호 / 승인권자 / 개정이력] 4대 필수 요소를 강제화하고, 공정별 입력(Input)-출력(Output) 및 KPI 지표를 정의하세요.",
                "template_snippet": "본 절차서의 제·개정은 품질보증팀장의 검토 및 대표이사 승인을 득하여야 하며, 문서 상단에 [문서번호 / 개정번호(Rev.) / 시행일자 / 승인권자 서명]을 명시하고 구본은 '폐기(Obsolete)' 스탬프 날인 후 회수한다.",
            },
            {
                "clause": "ISO 9001 8.7 / 10.2 (고객만족·부적합 통제 및 8D 시정조치)",
                "title": "부적합 산출물 격리 식별, 고객 불만 피드백 및 8D Report 기반 재발방지 절차 누락",
                "keywords": ["부적합", "격리", "고객만족", "불만", "시정조치", "재발방지", "원인분석", "capa"],
                "remediation": "부적합품 발견 시 즉시 식별·격리(Hold)하는 절차를 명문화하고, 고객 불만 및 공정 부적합에 대한 8D Report 단계별 액션과 시정조치 유효성 평가를 기록하세요.",
                "template_snippet": "공정 및 출하검사 중 부적합 발생 시 즉시 적색 부적합 라벨을 부착하여 MRB(부적합품 격리구역)로 격리(D3 봉쇄조치)하고, 5-Why 근본원인 분석(D4) 및 시정·예방조치(D5~D7) 완료 후 3개월간 재발 여부를 유효성 검증한다.",
            },
        ],
    },
    "ISO 13485": {
        "full_name": "ISO 13485:2016 의료기기 품질경영시스템 (MD-QMS)",
        "triggers": ["iso 13485", "iso13485", "의료기기 품질", "의료기기 매뉴얼", "의료기기 제조", "mdf"],
        "clauses": [
            {
                "clause": "ISO 13485 4.2.3 (의료기기 파일 MDF & 식약처 기술문서 심사 연계)",
                "title": "제품 기술문서(식약처 기술문서 심사 항목)·제조공정·측정 및 모니터링 스펙 정의 누락",
                "keywords": ["mdf", "의료기기 파일", "기술문서", "제품사양", "도면", "제조공정", "모니터링", "작업표준", "규격"],
                "remediation": "식약처 기술문서 심사(모양 및 구조·원재료·성능·시험규격)와 일치하는 제품군별 의료기기 파일(MDF) 인덱스를 신설하고 BOM, 도면, 공정흐름도(PFC), 검사기준서(SIP)의 상호 참조 번호를 명시하세요.",
                "template_snippet": "품질보증책임자는 품목별 의료기기 파일(MDF) 및 식약처 기술문서 심사 허가증(원재료·성능·시험규격)을 최신본으로 유지하며, 설계·원재료 변경 시 식약처 기술문서 변경심사 완료 후 양산 공정(DMR)에 반영한다.",
            },
            {
                "clause": "ISO 13485 4.2.4 / 4.2.5 (문서 및 기록 관리·법정 보존기한)",
                "title": "문서번호·개정번호·승인권자·개정이력 및 의료기기 수명주기 기록 보존기한 누락",
                "keywords": ["문서번호", "개정번호", "rev", "승인", "결재", "개정이력", "보존기한", "보관기간"],
                "remediation": "표준 문서 헤더에 [문서번호 / 개정번호 / 승인권자 / 개정이력표]를 포함하고, 품질 기록의 보존기한을 '의료기기 수명주기 또는 제품 출하 후 최소 2년 이상'으로 명시하세요.",
                "template_snippet": "모든 품질문서는 발행 전 승인권자의 적격성 검토·승인을 거치며, 제조이력서(DHR) 및 멸균·검사 기록은 당사 지정 의료기기 유효기한(수명주기) 경과 후 최소 2년 이상 위·변조 방지 상태로 보존한다.",
            },
            {
                "clause": "ISO 13485 7.5.6 (공정 밸리데이션 & 멸균 밸리데이션 ISO 11135/11137 연계)",
                "title": "특수 공정 IQ/OQ/PQ 적격성 평가, 멸균 밸리데이션(ISO 11135/11137) 및 공정능력(Cpk >= 1.33 / Ppk >= 1.67) 판정 기준 누락",
                "keywords": ["밸리데이션", "validation", "iq", "oq", "pq", "적격성", "공정능력", "cpk", "재밸리데이션", "11135", "11137", "설비 검증", "검증 프로토콜"],
                "remediation": "결과를 전수 검증할 수 없는 특수 공정(EO 멸균 ISO 11135, 감마선 멸균 ISO 11137, 실링 ISO 11607)에 대해 IQ/OQ/PQ 프로토콜 번호와 공정능력지수(초기 Ppk >= 1.67, 양산 Cpk >= 1.33) 판정 기준 및 연 1회 정기 재밸리데이션 주기를 규정하세요.",
                "template_snippet": "멸균(ISO 11135 EO가스 / ISO 11137 방사선) 및 파우치 열밀봉(실링) 특수 공정은 양산 전 IQ(설치)·OQ(운전)·PQ(성능) 적격성 평가를 완료해야 하며, 핵심 파라미터(온도·압력·밀봉강도)는 초기 Ppk >= 1.67, 양산 Cpk >= 1.33 이상을 유지하고 연 1회 정기 재밸리데이션을 수행한다.",
            },
            {
                "clause": "ISO 13485 7.5.8 / 7.5.9 (식별·LOT 추적성 및 UDI 고유기기식별자 표시)",
                "title": "원자재~완제품 LOT 양방향 추적성(Traceability) 및 UDI 고유기기식별자 표시·부적합품 격리 절차 누락",
                "keywords": ["lot", "로트", "추적성", "식별", "udi", "바코드", "이력", "수입검사", "격리"],
                "remediation": "원자재 입고 LOT 번호가 제조이력서(DHR) 및 완제품 출하 라벨의 UDI 고유기기식별자(UDI-DI/UDI-PI 바코드)까지 1:1 양방향 추적되도록 LOT 부여 규칙과 부적합품 적색 라벨 격리 절차를 추가하세요.",
                "template_snippet": "모든 원자재 및 반제품은 고유 LOT 번호로 식별하며, 완제품 포장 라벨에는 식약처 및 국제 표준에 따른 UDI 고유기기식별자(UDI-DI 품목식별자 + UDI-PI 제조단위·유효기한 바코드)를 표시하여 원자재 입고부터 최종 출하처까지 100% 양방향 추적성을 보장한다.",
            },
            {
                "clause": "ISO 13485 8.5.2 / 8.5.3 (시정·예방조치 CAPA 및 8D Report 단계별 액션)",
                "title": "5-Why 근본원인 규명, 8D Report 단계별 액션 및 CAPA 유효성 검증 기준 누락",
                "keywords": ["capa", "시정조치", "예방조치", "5-why", "근본원인", "8d", "재발방지", "부적합", "car"],
                "remediation": "단순 현상 수정(Correction)과 근본원인 제거(Corrective Action)를 구분하고, 불량 발생 시 [D3 긴급봉쇄 ➔ D4 5-Why 원인분석 ➔ D5 CAPA 수립 ➔ D6 3개월 유효성 검증 ➔ D7 수평전개] 8D Report 단계별 액션을 의무화하세요.",
                "template_snippet": "공정 부적합 및 기준 이탈 발생 시 24시간 내 D3 긴급 봉쇄조치(MRB 격리)를 시행하고, 8D Report 절차에 따라 5-Why 근본원인 분석(D4), 시정·예방조치 실행(D5), 후속 3개 LOT 이상 공정능력(Cpk >= 1.33) 유효성 검증(D6) 및 표준 작업표준서 개정·수평전개(D7)를 수행한다.",
            },
        ],
    },
    "ISO 14971": {
        "full_name": "ISO 14971:2019 의료기기 위험관리 (Risk Management)",
        "triggers": ["iso 14971", "iso14971", "위험관리", "위해요인", "잔여위험", "rpn"],
        "clauses": [
            {
                "clause": "ISO 14971 5.2~5.5 (위해요인 식별 및 위험 산정 RPN)",
                "title": "정상·고장 상태 위해요인(Hazard) 식별 및 심각도(S)×발생빈도(O) 위험 매트릭스 산정 누락",
                "keywords": ["위해요인", "hazard", "심각도", "발생빈도", "rpn", "위험산정", "매트릭스", "위험도"],
                "remediation": "식약처 기술문서 심사 첨부자료 요건에 맞춰 생물학적·전기적·기계적·멸균실패·사용오류 위해요인(Hazard)을 전수 도출하고, 심각도(S 1~5등급)와 발생가능성(O 1~5등급) 매트릭스로 초기 위험도(RPN)를 산정하세요.",
                "template_snippet": "당사 의료기기의 정상 및 단일고장 상태에서 발생 가능한 위해요인(생물학적 오염, 포장 파손, 방사선/EO 잔류물 등)을 식별하고, 위험관리계획서(RMP)의 심각도(S)×발생빈도(O) 5×5 매트릭스에 따라 RPN 점수를 정량 산정한다.",
            },
            {
                "clause": "ISO 14971 7.1~7.4 (위험통제 3단계 조치 및 잔여위험 평가)",
                "title": "설계 본질안전 ➔ 방호수단 ➔ 안전정보(UDI·라벨링) 3단계 위험통제 및 잔여위험 수용성 평가 누락",
                "keywords": ["위험통제", "본질안전", "잔여위험", "수용", "이득", "fmea", "완화"],
                "remediation": "위험통제 우선순위(① 본질안전 설계 ➔ ② 제조공정·설비 방호 알람 ➔ ③ 사용설명서 및 UDI 라벨 경고)를 적용한 뒤 통제 후 개별·전체 잔여위험(Residual Risk) 수용성 평가와 위험/이득(Benefit-Risk) 분석을 문서화하세요.",
                "template_snippet": "식별된 중·고위험 항목은 [1순위: 본질안전 설계 변경 ➔ 2순위: 공정 인터락 및 알람 설치 ➔ 3순위: 사용설명서(IFU) 및 UDI 라벨 경고 문구 기재] 순으로 통제하며, 통제 후 잔여위험이 수용 기준(ALARP) 이내임을 검증하여 위험관리보고서(RMR)에 기록한다.",
            },
            {
                "clause": "ISO 14971 10 (생산 및 생산 후 정보 수집·FMEA 및 CAPA 연계)",
                "title": "시판 후 임상·불만·공정능력(Cpk) 데이터 기반 위험관리파일(RMF) 및 P-FMEA 주기적 갱신 절차 누락",
                "keywords": ["rmf", "위험관리파일", "시판후", "pms", "갱신", "fmea", "연계"],
                "remediation": "생산 공정능력(Cpk < 1.33 미달) 및 시판 후 감시(PMS, 고객 불만, 부작용) 데이터가 발생할 경우 위험관리파일(RMF)과 D-FMEA/P-FMEA, 8D CAPA를 연동 업데이트하는 환류 절차를 수립하세요.",
                "template_snippet": "제조 공정검사 부적합, CAPA 발생 또는 시판 후 감시(PMS)에서 신규 위해요인이 확인될 경우, 15일 이내에 공정 FMEA(P-FMEA)와 위험관리파일(RMF)의 발생빈도 등급을 재산정하고 위험통제 유효성을 재검증한다.",
            },
        ],
    },
    "IEC 60601 / IEC 62304": {
        "full_name": "IEC 60601-1 (전자의료기기 전기·기계 안전성) & IEC 62304 (의료기기 SW 수명주기)",
        "triggers": ["iec 60601", "iec60601", "60601", "iec 62304", "iec62304", "62304", "누설전류", "의료기기 sw", "소프트웨어 안전등급"],
        "clauses": [
            {
                "clause": "IEC 60601-1 (전자의료기기 전기·기계적 안전성 및 식약처 기술문서 시험규격)",
                "title": "환자 누설전류·접지연속성·내전압(2중 절연 MOPP/MOOP) 및 기계적 강도 안전 기준 누락",
                "keywords": ["누설전류", "절연", "내전압", "접지", "전기안전", "기계적", "온도상승"],
                "remediation": "식약처 기술문서 심사 시험규격에 부합하도록 장착부(Type B/BF/CF) 등급별 환자 누설전류 허용한도, 2중 절연(2 MOPP) 내전압 시험 및 외장 기계적 강도 시험 기준치를 명시하세요.",
                "template_snippet": "전자의료기기 출하 전 전수 안전성 시험으로 접지연속성(0.1Ω 이하), 내전압 시험(1,500V~4,000V AC, 2 MOPP 절연 파괴 없을 것) 및 장착부(Type BF/CF) 환자 누설전류 허용치를 측정하여 제조이력서(DHR)에 기록한다.",
            },
            {
                "clause": "IEC 60601-1-2 (전자파 적합성 EMC 시험 및 필수성능 유지)",
                "title": "전자파 방사(EMI) 및 정전기·서지 내성(EMS) 규격 검증 기준 누락",
                "keywords": ["emc", "emi", "ems", "전자파", "정전기", "esd", "내성"],
                "remediation": "IEC 60601-1-2 4.1판 기준에 따른 전자파 장해(EMI) 및 정전기 방전(ESD ±8kV 접촉 / ±15kV 기중)·서지 내성(EMS) 필수 시험 조건과 필수성능(Essential Performance) 유지 기준을 정의하세요.",
                "template_snippet": "본 기기는 IEC 60601-1-2 전자파 안전 규격에 따라 정전기 방전(ESD 접촉 ±8kV, 기중 ±15kV) 및 방사성 RF 전자기장 내성 시험 중에도 임상적 필수성능(Essential Performance)의 저하 또는 오작동이 없어야 한다.",
            },
            {
                "clause": "IEC 62304 (의료기기 SW 안전 등급 Class A/B/C 및 수명주기 추적성)",
                "title": "SW 안전 등급(Class A/B/C) 분류, 요구사항 추적성(SRS-SDS-Test) 및 SOUP 보안 관리 누락",
                "keywords": ["class a", "class b", "class c", "안전등급", "srs", "추적성", "soup", "단위테스트", "수명주기"],
                "remediation": "SW 고장 시 상해 심각도에 따라 안전 등급(Class A: 경미 / B: 비심각 / C: 사망·중상)을 분류하고, 요구사항(SRS)-아키텍처(SDS)-소스코드-단위/통합시험 간 양방향 추적성 매트릭스를 구축하세요.",
                "template_snippet": "의료기기 소프트웨어는 IEC 62304에 의거 안전 등급(Class A/B/C)을 부여하며, 소프트웨어 요구사항 명세서(SRS)부터 상세설계(SDS), 단위 코드 검증 및 시스템 밸리데이션 시험결과서까지 1:1 양방향 추적성 매트릭스를 유지한다.",
            },
        ],
    },
    "KGMP / FDA 21 CFR Part 820": {
        "full_name": "식약처 의료기기 KGMP (기술문서·UDI) & 미국 FDA 21 CFR Part 820 (QMSR)",
        "triggers": ["kgmp", "fda", "21 cfr", "part 820", "qmsr", "dmr", "dhr"],
        "clauses": [
            {
                "clause": "KGMP / 21 CFR 820.181 & 820.184 (식약처 기술문서 연계 DMR·DHR 및 UDI 관리)",
                "title": "식약처 기술문서 심사 사양과 일치하는 제품표준서(DMR)·제조이력서(DHR) 및 UDI 고유기기식별자 기록 누락",
                "keywords": ["dmr", "dhr", "제품표준서", "제조이력", "제조지시", "배치기록", "작업일지", "수율"],
                "remediation": "식약처 기술문서 심사 허가 사양과 일치하는 제품표준서(DMR) 및 로트별 제조이력서(DHR) 양식을 수립하고, 투입 원자재 LOT·멸균 밸리데이션(ISO 11135/11137) 파라미터·UDI 고유기기식별자 라벨 검수 서명이 누락 없이 기록되도록 통제하세요.",
                "template_snippet": "제조부서는 식약처 기술문서 심사 허가 사양이 반영된 제품표준서(DMR)에 의거 로트별 제조지시 및 기록서(DHR)를 발행하며, 공정 완료 시 작업자·품질검수자 이중 서명과 UDI 고유기기식별자 바코드 인쇄 적격 견본을 DHR에 첨부한다.",
            },
            {
                "clause": "KGMP / 21 CFR 820.198 (고객 불만처리·이상사례 MDR 보고 및 8D CAPA)",
                "title": "고객 불만 접수·8D 조사 및 식약처/FDA 이상사례(MDR) 법정 보고 기한 준수 절차 누락",
                "keywords": ["불만", "부작용", "이상사례", "mdr", "보고", "식약처", "fda", "피드백"],
                "remediation": "모든 고객 불만을 품질보증부서에서 8D Report 절차로 조사하고, 사망·중대한 부작용 관련 시 법정 기한 내에 식약처(의료기기 이상사례 보고) 및 미국 FDA(eMDR)에 보고하는 비상 절차를 명시하세요.",
                "template_snippet": "고객 불만 및 부작용 접수 시 품질보증팀은 즉시 8D Report 기반 원인 조사에 착수하며, 사망 또는 중대한 건강 피해가 우려되는 이상사례(MDR)는 인지 후 법정 기한 내에 식약처 및 FDA에 즉시 보고한다.",
            },
            {
                "clause": "KGMP / 21 CFR Part 806 (제품 회수 Recall 및 UDI 유통망 추적)",
                "title": "부적합 출하 제품 UDI 추적·회수(Recall) 등급 분류 및 모의 회수 훈련 절차 누락",
                "keywords": ["회수", "recall", "리콜", "출하정지", "추적", "폐기", "통보"],
                "remediation": "위해도에 따른 회수 등급(1·2·3등급) 분류 기준, UDI 고유기기식별자 기반 유통망 거래처 긴급 통보 양식, 회수품 MRB 격리·폐기 및 연 1회 이상 모의 회수(Mock Recall) 훈련 절차를 규정하세요.",
                "template_snippet": "중대한 품질 부적합 출하 인지 시 즉시 회수대책위원회를 소집하여 UDI 고유기기식별자 및 LOT 추적 기록으로 납품 의료기관을 특정하고, 식약처 회수계획서 보고 및 전량 회수·격리(연 1회 모의 회수 훈련 의무화)를 실시한다.",
            },
        ],
    },
    "IATF 16949": {
        "full_name": "IATF 16949:2016 자동차·전장 부품 품질경영시스템 (5 Core Tools)",
        "triggers": ["iatf 16949", "iatf16949", "16949", "apqp", "ppap", "msa", "core tools", "자동차 품질", "전장부품 품질", "전장부품 수입검사"],
        "clauses": [
            {
                "clause": "IATF 16949 Core Tool 1 & 2 (APQP 선행제품품질계획 & PPAP 부품승인)",
                "title": "단계별 게이트 리뷰(APQP) 및 양산 부품 승인 제출물 18종(PPAP PSW) 검증 절차 누락",
                "keywords": ["apqp", "ppap", "psw", "선행품질", "부품승인", "control plan", "관리계획서", "초도품"],
                "remediation": "개발 5단계 APQP 일정과 연동하여 공정흐름도(PFD)-PFMEA-관리계획서(Control Plan) 3대 문서의 일관성을 확보하고, 양산 전 PPAP 18종 승인원(PSW) 및 초기공정능력(Ppk >= 1.67) 검증 결과를 제출하세요.",
                "template_snippet": "신규 전장부품 개발 시 APQP 5단계 게이트 리뷰를 통해 공정흐름도(PFD)-공정FMEA-관리계획서(Control Plan)의 특별특성 번호를 1:1 동기화하며, 양산 초도품 출하 전 PPAP Level 3 기준 18종 서류 및 PSW(부품제출보증서) 승인을 완료한다.",
            },
            {
                "clause": "IATF 16949 Core Tool 3 & 4 (AIAG-VDA FMEA & MSA 측정시스템분석)",
                "title": "설계·공정 FMEA 조치우선순위(AP) 관리 및 게이지 R&R(%GRR < 10%) 적격성 평가 누락",
                "keywords": ["fmea", "pfmea", "msa", "게이지", "grr", "r&r", "측정시스템", "검교정", "편향"],
                "remediation": "관리계획서에 명시된 모든 측정기기에 대해 게이지 R&R(%GRR < 10%: 적격, 10~30%: 조건부 수용, >30%: 부적합) 및 편향·선형성 분석을 수행하고 AIAG-VDA FMEA 고위험(AP: High) 항목의 8D 개선대책을 수립하세요.",
                "template_snippet": "관리계획서(Control Plan)에 등록된 모든 검사 계측기는 양산 적용 전 MSA 게이지 R&R을 실시하여 %GRR < 10% 및 구분범주수(ndc >= 5) 적격 판정을 확보해야 하며, 부적합 계측기는 즉시 현장 사용을 중단하고 검교정을 실시한다.",
            },
            {
                "clause": "IATF 16949 Core Tool 5 (SPC 통계적 공정관리 & Cpk >= 1.33 / Ppk >= 1.67 판정 기준)",
                "title": "특별특성(CC/SC) 관리도(Xbar-R) 실시간 모니터링, 공정능력지수(Ppk >= 1.67, Cpk >= 1.33) 및 8D Report 액션 누락",
                "keywords": ["spc", "cpk", "ppk", "관리도", "xbar", "통계적", "특별특성", "산포"],
                "remediation": "핵심 특별특성(CC/SC)에 대해 초기 공정능력 Ppk >= 1.67, 양산 유지 공정능력 Cpk >= 1.33 판정 기준을 설정하고, 미달 또는 관리한계선(UCL/LCL) 이탈 시 즉시 8D Report 단계별 액션(D3 전수선별 ➔ D4 5-Why ➔ D5~D7 CAPA)을 가동하세요.",
                "template_snippet": "특별특성(CC/SC) 공정은 Xbar-R 관리도를 통해 상시 모니터링하며, 초도 양산 시 Ppk >= 1.67, 정규 양산 시 Cpk >= 1.33 이상을 유지해야 한다. Cpk < 1.33 미달 시 즉시 100% 전수선별(Containment)로 전환하고 8D Report 시정조치를 발동한다.",
            },
        ],
    },
    "ISO 14001 / ISO 45001": {
        "full_name": "ISO 14001:2015 (환경경영) & ISO 45001:2018 (안전보건경영시스템)",
        "triggers": ["iso 14001", "iso14001", "14001", "iso 45001", "iso45001", "45001", "환경경영", "안전보건경영", "위험성평가", "아차사고"],
        "clauses": [
            {
                "clause": "ISO 14001 6.1.2 (환경측면 식별 및 환경영향평가)",
                "title": "전과정(LCA) 관점 대기·수질·폐기물·에너지 환경측면 식별 및 중요 환경측면 관리 기준 누락",
                "keywords": ["환경측면", "환경영향", "폐기물", "배출", "온실가스", "에너지", "lca"],
                "remediation": "정상·비정상·비상시 활동에서 발생하는 환경측면(대기배출, 폐수, 지정폐기물, 화학물질)을 식별하고 환경영향평가 점수표를 통해 중요 환경측면 저감 목표를 수립하세요.",
                "template_snippet": "원부자재 입고부터 제조·폐기까지 전과정(LCA)의 환경측면을 연 1회 식별·평가하며, 유의성 기준 점수를 초과한 중요 환경측면은 연간 환경목표 및 저감 실행계획(EMP)을 수립하여 분기별로 실적을 점검한다.",
            },
            {
                "clause": "ISO 45001 6.1.2 (사업장 위험성평가 및 아차사고 발굴)",
                "title": "유해·위험요인 파악, 근로자 참여형 위험성평가 및 아차사고(Near-Miss) 개선 절차 누락",
                "keywords": ["위험성평가", "아차사고", "near-miss", "유해위험", "안전보호구", "작업환경", "재해"],
                "remediation": "정기 및 수시 위험성평가에 현장 작업자 참여를 보장하고, 아차사고(Near-Miss) 발굴 보고 제도와 공학적 방호조치(인터락·안전가드) 개선 이력을 기록하세요.",
                "template_snippet": "설비 신설·변경 및 정기 위험성평가 시 현장 작업자가 직접 참여하여 유해·위험요인을 발굴하며, 위험도 허용 기준 초과 공정은 안전 인터락·방호가드 등 공학적 개선 대책을 완료한 후 작업을 개시한다.",
            },
            {
                "clause": "ISO 14001 / 45001 8.2 & 9.1.2 (비상사태 대응 및 법규준수 평가)",
                "title": "화재·누출·중대재해 비상대응 시나리오 훈련 및 환경·산업안전 법규준수 평가표 누락",
                "keywords": ["비상사태", "비상대응", "소방", "누출", "법규", "산업안전", "훈련"],
                "remediation": "화학물질 유출·화재·산업재해 발생 시 비상연락망과 초기 대응 시나리오 모의훈련을 반기별로 실시하고, 환경·안전보건 법규 등록부 및 준수 평가표를 최신화하세요.",
                "template_snippet": "유해화학물질 누출 및 화재·중대재해 비상대응 시나리오에 따른 반기별 모의 대피·방재 훈련을 실시하고, 산업안전보건법 및 환경 관련 법규 준수 여부를 반기 1회 정량 평가하여 경영검토에 보고한다.",
            },
        ],
    },
    "RoHS / REACH": {
        "full_name": "EU RoHS 지침 (유해물질 제한) & REACH 규정 (SVHC 고위험성물질 관리)",
        "triggers": ["rohs", "reach", "svhc", "중금속", "msds", "카드뮴", "6가크롬", "프탈레이트"],
        "clauses": [
            {
                "clause": "RoHS 2 (EU 2015/863) 4대 중금속 및 6대 브롬계·프탈레이트 허용농도",
                "title": "카드뮴(Cd ≤ 100ppm), 납·수은·6가크롬·PBB·PBDE·프탈레이트 4종(≤ 1,000ppm) 기준 검증 누락",
                "keywords": ["cd", "카드뮴", "pb", "납", "hg", "수은", "cr6", "6가크롬", "pbb", "pbde", "dehp", "100ppm", "1000ppm"],
                "remediation": "균질재질(Homogeneous Material) 단위 공인기관 정밀분석(ICP-OES/GC-MS) 성적서를 확보하여 Cd <= 100 ppm(0.01%), Pb/Hg/Cr6+/PBB/PBDE/DEHP/BBP/DBP/DIBP <= 1,000 ppm(0.1%) 적합 여부를 판정하고 초과 시 8D Report 봉쇄조치를 시행하세요.",
                "template_snippet": "모든 입고 부품은 균질재질 기준 RoHS 10대 제한물질 허용농도(Cd <= 100ppm, Pb·Hg·Cr6+·PBB·PBDE·프탈레이트 4종 <= 1,000ppm, 사내 안전관리기준 80% 이내)를 충족해야 하며, 기준 초과 검출 시 즉시 LOT 전량 반품 및 협력사 8D Report 시정조치를 명령한다.",
            },
            {
                "clause": "REACH SVHC (고위험성우려물질) 및 MSDS(물질안전보건자료) 통제",
                "title": "완제품 내 SVHC 후보물질 0.1 wt% 초과 여부 확인 및 최신 국문/영문 MSDS 비치 누락",
                "keywords": ["reach", "svhc", "msds", "물질안전보건자료", "화학물질", "성분표", "cas"],
                "remediation": "유럽화학물질청(ECHA) 최신 SVHC 후보물질 리스트 대비 부품 내 함량(0.1 wt% 미만) 보증서를 징구하고, 현장 취급 화학물질의 16대 항목 MSDS를 최신본으로 비치하세요.",
                "template_snippet": "협력사는 ECHA 최신 SVHC 고위험성우려물질이 중량 기준 0.1 wt%(1,000ppm) 이상 함유되지 않았음을 보증하는 비함유보증서와 16대 항목이 완비된 최신 MSDS(물질안전보건자료)를 초도 입고 전 제출하여야 한다.",
            },
            {
                "clause": "친환경 원부자재 CoA·ICP 공인성적서 유효기한(1년) 및 비전격리 관리",
                "title": "협력사 로트별 CoA 및 연간 ICP 정밀성적서 갱신 주기 인터락 누락",
                "keywords": ["icp", "공인성적서", "유효기간", "1년", "보증서", "비할로겐", "무연", "pb-free"],
                "remediation": "협력사 부품별 공인 시험성적서(유효기한 1년 이내) 만료일을 시스템에서 자동 추적하고, 무연(Pb-Free) 공정과 유연 공정의 혼입 방지 식별 관리 절차를 수립하세요.",
                "template_snippet": "수입검사(IQC) 부서는 부품별 공인기관 ICP 정밀분석 성적서의 유효기한(발행일로부터 1년)을 ERP 입고 인터락으로 통제하며, 만료 30일 전 미갱신 협력사 LOT는 입고 승인을 자동 보류한다.",
            },
        ],
    },
}


SYSTEM_GENERATED_PREFIXES = (
    "• [규격 적합성 정량 진단 요약",
    "[규격 적합성 정량 진단 요약",
    "• [다중 규격",
    "[다중 규격",
    "• [real spc",
    "• [기준치 초과 품목 5-why",
    "• [capa(",
    "• [협력사별 line-stop",
    "• ⚠️ [잠재 산포 리스크 경고]",
    "- [",
)

SYSTEM_GENERATED_MARKERS = (
    "➔ [문서 내 누락된 필수 요구사항]:",
    "[실무 보완 문구 예시(template snippet)]:",
    "[부정·결여 표현 원문]:",
    "— 🚨 부적합/보완필요(gap)",
    "— ✅ 적합(compliant)",
    "— ✅ 적합(기준 확인)",
)


def _strip_system_generated_sections(text: str) -> str:
    """
    [자가 중독(Self-Poisoning) 원천 차단]
    1차 심사 결과문·템플릿 예시 문구·웹 크롤링 데이터가 규격 탐지나 부정어 필터에
    재유입되지 않도록 순수 원본 첨부 문서 텍스트만 남깁니다.
    """
    if not text:
        return ""
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        s = raw_line.strip()
        if not s:
            continue
        low = s.lower()
        if low.startswith(SYSTEM_GENERATED_PREFIXES):
            break
        if any(m in low for m in SYSTEM_GENERATED_MARKERS):
            continue
        # parse_uploaded_document 추출 래퍼("[문서 주요 내용 N]: ...") 벗겨내어 순수 원문만 복원
        s = re.sub(r"^[•\-\*]\s*\[(?:문서 주요 내용|PDF 핵심 문장)\s*\d+\]:\s*", "", s)
        if re.match(r"^[•\-\*]\s*\[첨부 (?:문서명|PDF 문서 전수 스캔)\]:", s):
            continue
        cleaned_lines.append(s)
    return "\n".join(cleaned_lines)


def detect_compliance_standards(text: str, prompt: str = "") -> Tuple[list[str], list[str]]:
    """
    [엄격한 규격 심사 의도 분리 & 자가 중독 차단]
    시스템 생성 요약문/템플릿이 섞이지 않은 순수 원본 문서(text)와 사용자 프롬프트(prompt)만 검사하며,
    문서 핵심 도메인에 맞는 최대 4개 규격에만 집중합니다.
    """
    pure_text = _strip_system_generated_sections(text or "")
    pure_text_low = pure_text.lower()
    prompt_low = (prompt or "").lower()
    combined = f"{pure_text_low}\n{prompt_low}"
    matched_registered: list[str] = []

    for std_key, std_info in COMPLIANCE_STANDARDS_REGISTRY.items():
        if any(trig in combined for trig in std_info["triggers"]):
            matched_registered.append(std_key)

    # 미등록 국제/국내 규격 패턴 탐지 (이미 ISO 13485 세부 조항에 통합된 멸균·포장 하위규격 11135/11137/11607 제외)
    unregistered_found: list[str] = []
    known_numbers = {"9001", "13485", "14971", "60601", "62304", "16949", "14001", "45001", "820", "806", "2859", "11135", "11137", "11607"}

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

    # 도메인 집중 캡: 다수 규격이 동시에 우연히 언급된 경우 프롬프트/원문 명시 빈도가 높은 핵심 규격 최대 4개로 제한
    if len(matched_registered) + len(unregistered_found) > 4:
        def _score_reg(std_k: str) -> int:
            trigs = COMPLIANCE_STANDARDS_REGISTRY[std_k]["triggers"]
            return sum(3 for t in trigs if t in prompt_low) + sum(2 for t in trigs if t in pure_text_low)

        matched_registered.sort(key=_score_reg, reverse=True)
        matched_registered = matched_registered[:4]
        remain = max(0, 4 - len(matched_registered))
        unregistered_found = unregistered_found[:remain]

    return matched_registered, unregistered_found


def is_compliance_audit_request(text: str, prompt: str = "") -> bool:
    reg_stds, unreg_stds = detect_compliance_standards(text, prompt)
    return len(reg_stds) > 0 or len(unreg_stds) > 0


# =====================================================================
# [규격 심사 문맥 부정어 필터 (Negation Filter)]
# 키워드가 존재하더라도 같은 문장 안에 결여·미수립 표현이 있으면 '적합' 판정을 뒤집는다.
# =====================================================================
NEGATION_MARKERS: list[str] = [
    "없음", "없다", "없습니다", "미수립", "생략", "미실시", "제외", "누락", "추후",
    "미작성", "안 함", "안함", "하지 않", "두지 않", "않는다", "않음", "미적용", "미정",
]

# [구조적·정량적 증빙 정규식 (Structural Evidence Patterns)]
# 조항 유형별로 '실제 문서에 있어야 할 증빙 포맷'을 정규식으로 검증한다.
STRUCTURAL_EVIDENCE_RULES: list[dict] = [
    {
        "clause_markers": ["4.2.4", "9001 7.5", "제1영역"],
        "label": "문서번호/개정번호 포맷(SOP-xxx · Rev.N)",
        "pattern": r"(rev\.?\s*\d+|sop-[a-z0-9]+|[a-z]{2,5}-[a-z]{0,4}-?\d{2,4})",
    },
    {
        "clause_markers": ["4.2.4"],
        "label": "기록 보존기한(N년)",
        "pattern": r"((보존|보관)[^\n]{0,30}?\d+\s*년|\d+\s*년[^\n]{0,12}(보존|보관))",
    },
    {
        "clause_markers": ["14971 5.2"],
        "label": "위험 산정 정량 지표(RPN · 심각도)",
        "pattern": r"(rpn|심각도|severity)",
    },
    {
        "clause_markers": ["7.5.6", "Core Tool 5"],
        "label": "공정능력 판정 기준값(Cpk 1.33 · Ppk 1.67)",
        "pattern": r"(1\.33|1\.67)",
    },
]


def _split_sentences(text: str) -> list[str]:
    raw = re.split(r"(?:\r?\n)+|(?<=[.!?。])\s+", text or "")
    return [s.strip() for s in raw if s and s.strip()]


def _find_negated_evidence(sentences: list[str], keywords: list[str]) -> Optional[str]:
    """키워드가 포함된 문장 중 부정/결여 표현이 함께 존재하는 첫 문장을 반환한다."""
    for sent in sentences:
        low = sent.lower()
        if any(kw in low for kw in keywords) and any(neg in low for neg in NEGATION_MARKERS):
            return sent
    return None


def _check_structural_evidence(clause_name: str, doc_text_lower: str) -> Tuple[list[str], list[str]]:
    """조항에 해당하는 구조적 증빙 패턴의 (충족 라벨, 미충족 라벨) 목록을 반환한다."""
    found, missing = [], []
    for rule in STRUCTURAL_EVIDENCE_RULES:
        if any(marker in clause_name for marker in rule["clause_markers"]):
            if re.search(rule["pattern"], doc_text_lower, flags=re.I):
                found.append(rule["label"])
            else:
                missing.append(rule["label"])
    return found, missing


def evaluate_iso_compliance(text: str, prompt: str = "", crawled_knowledge: str = "") -> str:
    """
    [확장형 다중 규격 레지스트리(Multi-Standard Compliance Registry) & 동적 폴백 심사 엔진]
    시스템 생성 요약문(자가 중독)을 배제한 순수 원본 텍스트 + 사용자 프롬프트만 정밀 심사하며,
    정돈된 조항별 정량 진단과 시정 가이드를 분리 산출합니다.
    """
    pure_text = _strip_system_generated_sections(text or "")
    combined = f"{pure_text}\n{prompt or ''}".lower()
    matched_stds, unregistered_stds = detect_compliance_standards(pure_text, prompt)

    if not matched_stds and not unregistered_stds:
        matched_stds = ["ISO 13485", "ISO 9001"]

    has_actual_doc = len(pure_text.strip()) > 80 and "[첨부 데이터 전수" not in pure_text
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
                "template_snippet": c.get("template_snippet", c["remediation"]),
            })

    # 미등록 규격(예: ISO 27001, HACCP 등) 폴백(Fallback) 동적 체크리스트 생성
    for unreg_name in unregistered_stds:
        std_titles.append(f"{unreg_name} 국제·국내 인증 기준")
        active_clauses.extend([
            {
                "std_key": unreg_name,
                "clause": f"{unreg_name} 제1영역 (문서화 체계·정책 및 표준 절차서 통제)",
                "title": f"{unreg_name} 매뉴얼·절차서(SOP) 제·개정 이력, 승인권자 및 조직 책임·권한 정의 누락",
                "keywords": ["문서번호", "개정번호", "승인", "절차서", "정책", "조직", "매뉴얼"],
                "remediation": f"{unreg_name} 인증 심사 기준에 부합하도록 표준 절차서(SOP)에 문서번호·개정이력·승인권자를 명시하고 전담 관리책임자(팀장급) 지정서를 구비하세요.",
                "template_snippet": f"본 {unreg_name} 표준 절차서는 문서번호·개정번호(Rev.)·시행일자 및 승인권자 서명을 포함하여 발행하며, 전담 관리책임자의 검토 없이 임의 변경할 수 없다.",
            },
            {
                "std_key": unreg_name,
                "clause": f"{unreg_name} 제2영역 (핵심 위험요소·중요관리점 식별 및 통제 기준)",
                "title": f"{unreg_name} 특화 리스크 평가, 한계기준(Critical Limit) 설정 및 모니터링 주기 누락",
                "keywords": ["위험", "리스크", "한계기준", "모니터링", "점검", "통제", "중요관리"],
                "remediation": f"{unreg_name} 요구사항에 따른 핵심 리스크/중요관리점(CCP·통제항목)을 도출하고 정량적 허용 한계치와 일일 모니터링 체크시트를 신설하세요.",
                "template_snippet": f"{unreg_name} 핵심 관리 공정에 대해 정량적 한계기준(Critical Limit)과 일일 모니터링 주기를 설정하고, 한계기준 이탈 시 즉시 격리 및 8D 시정조치를 가동한다.",
            },
            {
                "std_key": unreg_name,
                "clause": f"{unreg_name} 제3영역 (내부심사·기록 보존 및 시정·예방조치 CAPA)",
                "title": f"{unreg_name} 정기 내부심사, 한계이탈 시 즉각 개선조치(CAPA) 및 유효성 검증 기록 누락",
                "keywords": ["내부심사", "시정조치", "capa", "개선", "유효성", "보존", "교육훈련"],
                "remediation": f"{unreg_name} 사후심사 및 갱신심사 통과를 위해 연 1회 이상 내부심사 결과보고서, 임직원 정기 교육훈련 수료증, 부적합 발생 시 5-Why 기반 CAPA 이력철을 완비하세요.",
                "template_snippet": f"연 1회 이상 {unreg_name} 전 조항에 대한 내부심사를 수행하며, 도출된 부적합(Gap) 사항은 5-Why 근본원인 규명 및 CAPA 시정조치 후 3개월 내 유효성을 검증하여 기록을 3년간 보존한다.",
            },
        ])

    pass_clauses = []
    gap_clauses = []
    clause_lines = []
    negation_hit_count = 0

    doc_text_lower = pure_text.lower()
    doc_sentences = _split_sentences(pure_text)

    for idx, c in enumerate(active_clauses, start=1):
        matched_kws = [kw for kw in c["keywords"] if kw in combined]

        # ① 부정어 문맥 필터: 키워드가 있어도 같은 문장에 '없음/미수립/생략/누락/추후...'가 있으면 즉시 Gap
        negated_sent = _find_negated_evidence(doc_sentences, c["keywords"])
        if negated_sent:
            negation_hit_count += 1
            gap_clauses.append(c)
            neg_excerpt = re.sub(r"^[-•*·\s]+", "", re.sub(r"\s+", " ", negated_sent)).strip()[:70]
            clause_lines.append(
                f"• [{c['clause']} — 🚨 부적합/보완필요(Gap) — 부정/미수립 문맥 검출] ➔ "
                f"[부정·결여 표현 원문]: \"{neg_excerpt}\" ➔ [문서 내 누락된 필수 요구사항]: {c['title']}"
            )
            continue

        # ② 구조적·정량적 증빙 정규식 검증 (실제 문서가 첨부된 경우)
        evidence_found, evidence_missing = ([], [])
        if has_actual_doc:
            evidence_found, evidence_missing = _check_structural_evidence(c["clause"], doc_text_lower)

        if has_actual_doc and len(matched_kws) >= 2 and not evidence_missing:
            status = "✅ 적합(Compliant)"
            pass_clauses.append(c)
            evidence_note = f" [정량 증빙 확인: {' · '.join(evidence_found)}]" if evidence_found else ""
            clause_lines.append(
                f"• [{c['clause']} — {status}]: 필수 요구사항이 문서 내에 명확히 정의되어 심사 기준을 충족합니다.{evidence_note}"
            )
        elif has_actual_doc and len(matched_kws) >= 2 and evidence_missing:
            status = "🚨 부적합/보완필요(Gap) — 구조적 증빙 미검출"
            gap_clauses.append(c)
            clause_lines.append(
                f"• [{c['clause']} — {status}] ➔ [필수 증빙 포맷 누락]: {' · '.join(evidence_missing)} ➔ [문서 내 누락된 필수 요구사항]: {c['title']}"
            )
        elif not has_actual_doc and idx == 1 and len(matched_kws) >= 1:
            status = "✅ 적합(기준 확인)"
            pass_clauses.append(c)
            clause_lines.append(
                f"• [{c['clause']} — {status}]: 핵심 관리 기준이 수립되어 있습니다."
            )
        else:
            status = "🚨 부적합/보완필요(Gap)"
            gap_clauses.append(c)
            clause_lines.append(
                f"• [{c['clause']} — {status}] ➔ [문서 내 누락된 필수 요구사항]: {c['title']}"
            )

    total_c = len(active_clauses)
    pass_c = len(pass_clauses)
    gap_c = len(gap_clauses)
    compliance_score = round((pass_c / max(1, total_c)) * 100, 1)

    std_banner = " · ".join(matched_stds + unregistered_stds)
    negation_note = f" | 부정/미수립 문맥 검출 {negation_hit_count}건" if negation_hit_count else ""
    header_summary = (
        f"• [규격 적합성 정량 진단 요약 ({std_banner})]: 총 {total_c}개 필수 조항 점검 결과 "
        f"적합 {pass_c}건, 보완필요(Gap) {gap_c}건 (현재 규격 부합도 {compliance_score}%){negation_note}."
    )

    guide_lines = []
    for gc in gap_clauses[:8]:
        guide_lines.append(
            f"- [{gc['clause']}] ➔ [문서 내 누락된 필수 요구사항]: {gc['title']} ➔ [실무 보완 문구 예시(Template Snippet)]: \"{gc['template_snippet']}\""
        )

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

    m_plain = re.match(r"^[+-]?\d+(?:\.\d+)?$", re.sub(r"[,%\sA-Za-zμmMPap]+", "", s))
    if m_plain:
        bound = float(m_plain.group(0))
        dev = round(measured - bound, 3)
        return None, dev

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


def parse_spec_limits(spec_str: str) -> Tuple[Optional[float], Optional[float]]:
    """
    기준규격 문자열에서 (LSL, USL)을 추출한다.
    예) '15.0±0.5' -> (14.5, 15.5) / '24.0~24.4' -> (24.0, 24.4) / '120이상' -> (120, None) / '100이하' -> (None, 100)
    """
    s = str(spec_str or "").strip()
    if not s:
        return None, None
    m_tol = re.search(r"(\d+(?:\.\d+)?)\s*(?:±|\+\-|\+/-)\s*(\d+(?:\.\d+)?)", s)
    if m_tol:
        target, tol = float(m_tol.group(1)), float(m_tol.group(2))
        return round(target - tol, 6), round(target + tol, 6)
    m_range = re.search(r"(\d+(?:\.\d+)?)\s*(?:~|\-)\s*(\d+(?:\.\d+)?)", s)
    if m_range:
        low, high = float(m_range.group(1)), float(m_range.group(2))
        return min(low, high), max(low, high)
    m_min = re.search(r"(?:>=|이상|min)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:이상|min|\+)", s, flags=re.I)
    if m_min:
        return float(m_min.group(1) or m_min.group(2)), None
    m_max = re.search(r"(?:<=|이하|미만|max|<)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:이하|미만|max)", s, flags=re.I)
    if m_max:
        return None, float(m_max.group(1) or m_max.group(2))
    return None, None


def _parse_measured_number(val_str: str) -> Optional[float]:
    clean_val = re.sub(r"[,%\sA-Za-zμmMPap]+", "", str(val_str or ""))
    if re.match(r"^[+-]?\d+(?:\.\d+)?$", clean_val):
        return float(clean_val)
    return None


def compute_spc_capability(values: list[float], lsl: Optional[float], usl: Optional[float]) -> dict:
    """
    [Real SPC 통계적 공정관리 수학 연산]
    - 평균(Mean), 표본 표준편차(σ, statistics.stdev)
    - Cp  = (USL - LSL) / (6σ)                       (양측 규격일 때만)
    - Cpk = min((USL - Mean) / 3σ, (Mean - LSL) / 3σ) (단측 규격이면 존재하는 쪽만 사용)
    - 규격 여유도(Margin %) = 가장 가까운 규격 한계까지의 거리 / 공차폭(양측) 또는 한계값(단측)
    """
    n = len(values)
    mean = statistics.fmean(values) if n else float("nan")
    sigma = statistics.stdev(values) if n >= 2 else None
    cp: Optional[float] = None
    cpk: Optional[float] = None

    if sigma is not None and sigma > 0:
        if lsl is not None and usl is not None:
            cp = (usl - lsl) / (6 * sigma)
        sides = []
        if usl is not None:
            sides.append((usl - mean) / (3 * sigma))
        if lsl is not None:
            sides.append((mean - lsl) / (3 * sigma))
        cpk = min(sides) if sides else None
    elif sigma == 0 and n >= 2:
        cp = math.inf if (lsl is not None and usl is not None) else None
        cpk = math.inf

    # 측정값별 규격 여유도(%) — 경계 15% 이내면 Warning Zone
    margins: list[float] = []
    for v in values:
        if lsl is not None and usl is not None and usl > lsl:
            margins.append(min(usl - v, v - lsl) / (usl - lsl) * 100)
        elif usl is not None and usl != 0:
            margins.append((usl - v) / abs(usl) * 100)
        elif lsl is not None and lsl != 0:
            margins.append((v - lsl) / abs(lsl) * 100)

    return {
        "n": n,
        "mean": mean,
        "sigma": sigma,
        "cp": cp,
        "cpk": cpk,
        "margins": margins,
        "min_margin": min(margins) if margins else None,
    }


def _fmt_index(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    if math.isinf(v):
        return "∞"
    return f"{v:.2f}"


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
    spc_groups: dict[tuple, dict] = {}

    judge_idx = -1
    lot_idx = -1
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
        elif any(k in h_low for k in ["lot", "로트", "제조번호", "배치", "batch", "serial"]):
            lot_idx = idx
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
        if (0 <= spec_idx < len(masked_row)) and (0 <= val_idx < len(masked_row)):
            spec_ok, calc_dev = evaluate_spec_compliance(masked_row[spec_idx], masked_row[val_idx])
            auto_dev = calc_dev
            if not is_fail and not is_pass:
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

        lot_val = masked_row[lot_idx] if (0 <= lot_idx < len(masked_row) and masked_row[lot_idx]) else f"LOT-{r_num:02d}"
        vendor_name = masked_row[vendor_idx] if (0 <= vendor_idx < len(masked_row) and masked_row[vendor_idx]) else "기타/미상"
        item_name = masked_row[item_idx] if (0 <= item_idx < len(masked_row) and masked_row[item_idx]) else f"품목-{r_num}"
        check_name = masked_row[check_idx] if (0 <= check_idx < len(masked_row) and masked_row[check_idx]) else "치수/성분규격"
        spec_val = masked_row[spec_idx] if (0 <= spec_idx < len(masked_row) and masked_row[spec_idx]) else "기준규격"
        measured_val = masked_row[val_idx] if (0 <= val_idx < len(masked_row) and masked_row[val_idx]) else "측정치"

        explicit_dev_str = masked_row[dev_idx] if (0 <= dev_idx < len(masked_row) and masked_row[dev_idx]) else ""
        if explicit_dev_str:
            raw_diff = explicit_dev_str
        elif auto_dev is not None:
            raw_diff = f"{auto_dev:+.2f}"
        else:
            raw_diff = "규격이탈"

        if is_fail:
            fail_count += 1
            vendor_stats.setdefault(vendor_name, {"total": 0, "fail": 0})
            vendor_stats[vendor_name]["total"] += 1
            vendor_stats[vendor_name]["fail"] += 1
            pareto_key = f"{check_name}({item_name})" if check_idx != -1 else item_name
            defect_pareto_counts[pareto_key] = defect_pareto_counts.get(pareto_key, 0) + 1
            if str(raw_diff).startswith("-"):
                diff_display = f"미달 {raw_diff}"
            elif str(raw_diff).startswith("+"):
                diff_display = f"초과 {raw_diff}"
            else:
                diff_display = str(raw_diff)
            failed_items_records.append({
                "row": str(r_num),
                "lot": lot_val,
                "vendor": vendor_name,
                "item": item_name,
                "check": check_name,
                "spec": spec_val,
                "measured": measured_val,
                "diff": diff_display,
            })
            fail_details.append(
                f"• [원본 #{r_num}행 | {lot_val} | {item_name}({vendor_name})] {check_name}: "
                f"기준규격(Spec) '{spec_val}' 대비 실측값 '{measured_val}' 검출 ➔ 판정: 🚨 부적합 (초과/미달 편차: {diff_display})"
            )
        elif is_pass:
            pass_count += 1
            vendor_stats.setdefault(vendor_name, {"total": 0, "fail": 0})
            vendor_stats[vendor_name]["total"] += 1
            pass_details.append(
                f"• [원본 #{r_num}행 | {lot_val} | {item_name}({vendor_name})] {check_name}: "
                f"기준규격(Spec) '{spec_val}' 대비 실측값 '{measured_val}' 확인 ➔ 판정: ✅ 적격(합격) (규격 내 편차: {raw_diff})"
            )
        else:
            pass_details.append(f"• [데이터 행 #{r_num}행]: {row_str_join}.")

        # [Real SPC] 공차 규격이 있는 수치형 검사항목을 (품목, 검사항목, 규격) 단위로 그룹핑
        if (0 <= spec_idx < len(masked_row)) and (0 <= val_idx < len(masked_row)):
            g_lsl, g_usl = parse_spec_limits(masked_row[spec_idx])
            g_val = _parse_measured_number(masked_row[val_idx])
            if g_val is not None and (g_lsl is not None or g_usl is not None):
                g_key = (item_name, check_name, spec_val)
                grp = spc_groups.setdefault(g_key, {
                    "item": item_name, "check": check_name, "spec": spec_val,
                    "lsl": g_lsl, "usl": g_usl, "values": [], "rows": [], "fail": 0,
                })
                grp["values"].append(g_val)
                grp["rows"].append({"row": r_num, "lot": lot_val, "measured": measured_val, "value": g_val, "pass": bool(is_pass and not is_fail)})
                if is_fail:
                    grp["fail"] += 1

        if 0 <= val_idx < len(masked_row) and masked_row[val_idx]:
            p_name = masked_row[item_idx] if (0 <= item_idx < len(masked_row)) else f"행{r_num}"
            c_name = masked_row[check_idx] if (0 <= check_idx < len(masked_row)) else headers[val_idx]
            dev_info_parts = []
            if auto_dev is not None:
                dev_info_parts.append(f"편차 {auto_dev:+.2f}")
            elif 0 <= dev_idx < len(masked_row) and masked_row[dev_idx]:
                dev_info_parts.append(f"편차 {masked_row[dev_idx]}")
            if (0 <= spec_idx < len(masked_row)) and (0 <= val_idx < len(masked_row)):
                r_lsl, r_usl = parse_spec_limits(masked_row[spec_idx])
                r_gval = _parse_measured_number(masked_row[val_idx])
                if r_gval is not None and (r_lsl is not None or r_usl is not None):
                    r_margin = compute_spc_capability([r_gval], r_lsl, r_usl)["min_margin"]
                    if r_margin is not None:
                        dev_info_parts.append(f"여유도 {r_margin:.1f}%")
            extra_str = f" ({', '.join(dev_info_parts)})" if dev_info_parts else ""
            item_metric_list.append(f"{p_name}[{c_name}: {masked_row[val_idx]}{extra_str}]")

        if 0 <= dev_idx < len(masked_row) and masked_row[dev_idx]:
            clean_dev = re.sub(r"[,%\s]", "", str(masked_row[dev_idx]))
            if re.match(r"^[+-]?\d+(?:\.\d+)?$", clean_dev):
                try:
                    deviation_vals.append(float(clean_dev))
                except Exception:
                    pass
        elif auto_dev is not None:
            deviation_vals.append(auto_dev)

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

    if item_metric_list:
        lines.append(f"• [항목별 실측치(단위별 분리) 및 개별 편차·규격 여유도]: {', '.join(item_metric_list[:12])}.")

    # =================================================================
    # [Real SPC: 표준편차 σ · Cp · Cpk · 규격 여유도 정밀 연산 + 잠재 산포 리스크 경고]
    # =================================================================
    spc_meta: list[dict] = []
    spc_warning_lines: list[str] = []
    spc_parts: list[str] = []

    def _g(x: Optional[float]) -> str:
        return "-" if x is None else f"{x:g}"

    for grp in spc_groups.values():
        cap = compute_spc_capability(grp["values"], grp["lsl"], grp["usl"])
        label = f"{grp['item']}-{grp['check']}"
        limit_str = f"LSL {_g(grp['lsl'])} / USL {_g(grp['usl'])}"
        min_margin = cap["min_margin"]
        margin_str = f"{min_margin:.1f}%" if min_margin is not None else "N/A"

        if cap["n"] >= 2 and cap["sigma"] is not None:
            cpk_v = cap["cpk"]
            if cpk_v is None:
                verdict = "판정 보류"
            elif cpk_v >= 1.67:
                verdict = "🟢 공정능력 우수(Cpk ≥ 1.67)"
            elif cpk_v >= 1.33:
                verdict = "🟢 공정능력 적정(Cpk ≥ 1.33)"
            else:
                verdict = "🚨 공정능력 부족(Cpk < 1.33)"
            spc_parts.append(
                f"{label}(n={cap['n']}, {limit_str}): 평균 {cap['mean']:.4f}, σ={cap['sigma']:.4f}, "
                f"Cp={_fmt_index(cap['cp'])}, Cpk={_fmt_index(cpk_v)}, 최소 규격 여유도 {margin_str} ➔ {verdict}"
            )
            if cpk_v is not None and not math.isinf(cpk_v) and cpk_v < 1.33:
                if grp["fail"] == 0:
                    spc_warning_lines.append(
                        f"• ⚠️ [잠재 산포 리스크 경고] {label} (n={cap['n']}, σ={cap['sigma']:.4f}, Cp={_fmt_index(cap['cp'])}): "
                        f"현재 규격 내 합격이나 공정능력 부족(Cpk={cpk_v:.2f} < 1.33)으로 대량 불량 발생 위험"
                    )
                else:
                    spc_warning_lines.append(
                        f"• ⚠️ [잠재 산포 리스크 경고] {label} (n={cap['n']}, σ={cap['sigma']:.4f}, Cp={_fmt_index(cap['cp'])}): "
                        f"규격 이탈 {grp['fail']}건 포함 · 공정능력 부족(Cpk={cpk_v:.2f} < 1.33)으로 대량 불량 발생 위험"
                    )
        else:
            spc_parts.append(
                f"{label}(n={cap['n']}, {limit_str}): 실측 {cap['mean']:g}, σ 산출 불가(단일 표본) · 규격 여유도 {margin_str}"
            )

        # 개별 합격 LOT의 Warning Zone(규격 경계 15% 이내) 탐지
        for r_info, m in zip(grp["rows"], cap["margins"]):
            if r_info["pass"] and 0 <= m <= 15.0:
                spc_warning_lines.append(
                    f"• ⚠️ [잠재 산포 리스크 경고] [원본 #{r_info['row']}행 | {r_info['lot']}] {label}: "
                    f"현재 규격 내 합격이나 실측값 '{r_info['measured']}'이(가) 규격 경계 15% 이내 Warning Zone(규격 여유도 {m:.1f}%)에 위치하여 대량 불량 발생 위험"
                )

        spc_meta.append({
            "item": grp["item"],
            "check": grp["check"],
            "spec": grp["spec"],
            "lsl": grp["lsl"],
            "usl": grp["usl"],
            "n": cap["n"],
            "mean": round(cap["mean"], 6),
            "sigma": round(cap["sigma"], 6) if cap["sigma"] is not None else None,
            "cp": (round(cap["cp"], 4) if cap["cp"] is not None and not math.isinf(cap["cp"]) else cap["cp"]),
            "cpk": (round(cap["cpk"], 4) if cap["cpk"] is not None and not math.isinf(cap["cpk"]) else cap["cpk"]),
            "min_margin_pct": round(min_margin, 2) if min_margin is not None else None,
        })

    if spc_parts:
        lines.append(f"• [Real SPC 공정능력 분석 (σ·Cp·Cpk 수학 연산)]: {' | '.join(spc_parts[:8])}.")
    if spc_warning_lines:
        lines.extend(spc_warning_lines[:8])

    set_session_table(session_id, {
        "filename": filename,
        "headers": export_headers,
        "rows": structured_export_rows,
        "spc": spc_meta,
    })

    if failed_items_records:
        # 모든 부적합(NG) 품목별 맞춤형 5-Why 근본원인 분석 생성
        for rec in failed_items_records[:12]:
            chk_low = f"{rec['check']} {rec['item']}".lower()
            if any(k in chk_low for k in ["카드뮴", "납", "수은", "6가크롬", "cr6", "cd", "pb", "hg", "rohs", "유해물질", "허용농도"]):
                why_chain = (
                    f"① Why1(현상): {rec['check']} 허용기준({rec['spec']}) 대비 실측치({rec['measured']}, {rec['diff']}) 초과 검출 ➔ "
                    f"② Why2(공정/자재): 공급사({rec['vendor']}) 하위 원부자재 균질재질 내 제한물질 혼입 및 배합 통제 실패 ➔ "
                    f"③ Why3(계측): 협력사 출하 전 XRF/ICP-OES 유해물질 스크리닝 선별 누락 ➔ "
                    f"④ Why4(관리): RoHS 1년 주기 공인성적서 및 LOT별 CoA 상한 자동 인터락 미연동 ➔ "
                    f"⑤ Why5(시스템): 협력사 유해물질 비함유 관리체계 및 라인 투입 사전 차단 프로세스 부재."
                )
            elif any(k in chk_low for k in ["두께", "치수", "내경", "외경", "평탄도", "공차"]):
                why_chain = (
                    f"① Why1(현상): {rec['check']} 기준규격({rec['spec']}) 대비 실측치({rec['measured']}, {rec['diff']}) 공차 이탈 ➔ "
                    f"② Why2(공정): 공급사({rec['vendor']}) 도금 전류밀도·가공 이송 조건 또는 금형 마모 편차 발생 ➔ "
                    f"③ Why3(설비): 인라인 계측 센서 영점 교정(Calibration) 주기 경과 ➔ "
                    f"④ Why4(관리): 출하 전 SPC Xbar-R 관리도 및 공정능력(Cpk ≥ 1.33) 사전 경고 미작동 ➔ "
                    f"⑤ Why5(시스템): 협력사 출하검사(OQC)와 당사 수입검사(IQC) 간 실시간 CoA 인터락 부재."
                )
            else:
                why_chain = (
                    f"① Why1(현상): 기준규격({rec['spec']}) 대비 실측치({rec['measured']}, {rec['diff']}) 이탈 발생 ➔ "
                    f"② Why2(공정): 공급사({rec['vendor']}) 원료 순도·제조 배합 파라미터 편차 발생 ➔ "
                    f"③ Why3(설비): 검사 설비 검교정 및 조건 모니터링 주기 경과 ➔ "
                    f"④ Why4(관리): 출하 전 SPC 관리한계(UCL/LCL) 사전 경고 미작동 ➔ "
                    f"⑤ Why5(시스템): 협력사 출하검사(OQC)와 당사 수입검사(IQC) 간 실시간 CoA 인터락 부재."
                )
            lines.append(
                f"• [기준치 초과 품목 5-Why 근본원인 분석 (#{rec['row']}행 | {rec['lot']} | {rec['item']}({rec['vendor']}) - {rec['check']})]: {why_chain}"
            )

        # 협력사별 전수 그룹핑 기반 Line-Stop · SCAR · 8D CAPA 조치 생성
        vendor_ng_map: dict[str, list[dict[str, str]]] = {}
        for rec in failed_items_records:
            vendor_ng_map.setdefault(rec["vendor"], []).append(rec)

        for v_name, v_recs in vendor_ng_map.items():
            lot_summary = ", ".join(f"{r['lot']}({r['item']}·{r['check']} {r['measured']})" for r in v_recs[:6])
            lines.append(
                f"• [협력사별 Line-Stop · SCAR · 8D CAPA 조치 ({v_name})]: "
                f"[D3 긴급 봉쇄·Line-Stop] 부적합 {len(v_recs)}건({lot_summary}) 즉시 라인 투입·출하 전면 정지(Line-Stop) 및 MRB 적색 격리, ERP 해당 협력사 동일 품목 입고 보류 인터락 적용 | "
                f"[D4~D7 SCAR & 8D CAPA] {v_name} 대상 시정조치요구서(SCAR/8D Report) 7일 내 제출 명령, 유해물질 전수 ICP-OES/XRF 검증 및 후속 3개월 출하 LOT 공정능력지수(Cpk ≥ 1.33) 입증 완료 전 재입고 차단."
            )

        vendors_all = ", ".join(vendor_ng_map.keys())
        lines.append(
            f"• [CAPA(시정 및 예방조치) 및 8D 총괄 권고사항]: "
            f"[시정조치(Corrective Action)] 검출된 전 부적합 {len(failed_items_records)}개 LOT MRB 격리 및 해당 협력사({vendors_all}) 전원 대상 Line-Stop·SCAR/8D Report 발행 | "
            f"[예방조치(Preventive Action)] 전 품목 상·하한 Spec 자동 인터락 적용, 핵심 특성 Cpk ≥ 1.33 및 RoHS 공인성적서(1년 유효기간) ERP 연동 검증 의무화."
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
        "spc": spc_meta,
        "spc_warning_count": len(spc_warning_lines),
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
                for idx, s in enumerate(sents[:30], 1):
                    extracted_lines.append(f"• [PDF 핵심 문장 {idx}]: {s[:220]}.")
            if is_compliance_audit_request(clean_pdf, filename):
                meta["type"] = "ISO_COMPLIANCE_DOC"
                extracted_lines.append(evaluate_iso_compliance(clean_pdf, filename))
            return "\n".join(extracted_lines), meta

        txt, _ = scrub_pii_and_secrets(content.decode("utf-8", errors="ignore"))
        lines = [line.strip() for line in txt.splitlines() if len(line.strip()) > 5]
        out = [f"• [첨부 문서명]: {filename} (총 {len(lines)}줄)."]
        for idx, l in enumerate(lines[:60], 1):
            out.append(f"• [문서 주요 내용 {idx}]: {l[:220]}.")
        if is_compliance_audit_request(txt, filename):
            meta["type"] = "ISO_COMPLIANCE_DOC"
            out.append(evaluate_iso_compliance(txt, filename))
        return "\n".join(out), meta

    except Exception:
        return f"• [첨부 파일 로드]: {filename} ({meta['size_kb']}KB) 분석 준비 완료.", meta
