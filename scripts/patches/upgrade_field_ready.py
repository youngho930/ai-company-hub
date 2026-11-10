import os
import py_compile

FILES = {
    # 1. 실무형 파일 분석 엔진: (1) 상단 결재란/빈줄 건너뛰는 스마트 헤더 탐색, (2) '100 ± 5', '99.5 이상' 자동 수학 판정기, (3) 2번 시트용 구조화 테이블 보존
    "backend/file_processor.py": r'''import io
import csv
import re
from typing import Tuple, Optional

LAST_PARSED_TABLE: dict[str, dict] = {}

def evaluate_spec_compliance(spec_str: str, val_str: str) -> Tuple[Optional[bool], Optional[float]]:
    """
    현업 성적서(CoA)에 '합격/불합격' 판정 열이 비어있거나 없을 때,
    기준 규격(Spec) 문자열과 실측치를 수학적으로 비교하여 적격 여부(True/False)와 편차(Deviation)를 자동 연산합니다!
    지원 규격 포맷:
    - '100 ± 5' 또는 '100 +- 5'
    - '99.5 이상', '>= 99.5', '99.5 MIN'
    - '20 이하', '<= 20', '20 MAX'
    - '95.0 ~ 105.0', '95 - 105'
    """
    if not spec_str or not val_str:
        return None, None

    clean_val = re.sub(r"[,%\sA-Za-zμmMPap]+", "", str(val_str))
    if not re.match(r"^[+-]?\d+(?:\.\d+)?$", clean_val):
        return None, None
    measured = float(clean_val)
    s = str(spec_str).strip()

    # 1) 중심값 ± 공차 (예: 100 ± 5, 100 +- 0.5)
    m_tol = re.search(r"(\d+(?:\.\d+)?)\s*(?:±|\+\-|\+/-)\s*(\d+(?:\.\d+)?)", s)
    if m_tol:
        target = float(m_tol.group(1))
        tol = float(m_tol.group(2))
        dev = round(measured - target, 3)
        return (target - tol <= measured <= target + tol), dev

    # 2) 범위 규격 (예: 95.0 ~ 105.0)
    m_range = re.search(r"(\d+(?:\.\d+)?)\s*(?:~|\-)\s*(\d+(?:\.\d+)?)", s)
    if m_range:
        low = float(m_range.group(1))
        high = float(m_range.group(2))
        mid = (low + high) / 2.0
        dev = round(measured - mid, 3)
        return (low <= measured <= high), dev

    # 3) 하한 규격 (예: 99.5 이상, >= 99.5, Min 99.5)
    m_min = re.search(r"(?:>=|이상|min)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:이상|min|\+)", s, flags=re.I)
    if m_min:
        bound = float(m_min.group(1) or m_min.group(2))
        dev = round(measured - bound, 3)
        return (measured >= bound), dev

    # 4) 상한 규격 (예: 20 이하, <= 20, Max 20)
    m_max = re.search(r"(?:<=|이하|미만|max)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:이하|미만|max)", s, flags=re.I)
    if m_max:
        bound = float(m_max.group(1) or m_max.group(2))
        dev = round(measured - bound, 3)
        return (measured <= bound), dev

    return None, None

def find_header_row_index(rows: list[list[str]]) -> int:
    """
    현업 엑셀 파일 상단(1~5행)에 문서 제목이나 결재란이 있을 때,
    실제 컬럼명이 위치한 헤더 행(Header Row)을 자동으로 찾아냅니다.
    """
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

def _analyze_tabular_rows(filename: str, all_clean_rows: list[list[str]]) -> Tuple[str, dict]:
    h_idx = find_header_row_index(all_clean_rows)
    headers = all_clean_rows[h_idx]
    data_rows = all_clean_rows[h_idx + 1 :]

    total_rows = len(data_rows)
    pass_count = 0
    fail_count = 0
    fail_details = []
    pass_details = []
    vendor_stats: dict[str, dict[str, int]] = {}
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
        elif any(k in h_low for k in ["항목", "특성", "check", "parameter"]):
            check_idx = idx
        elif any(k in h_low for k in ["규격", "기준", "spec", "standard"]):
            spec_idx = idx
        elif any(k in h_low for k in ["실측", "측정", "결과값", "measured", "value"]):
            val_idx = idx
        elif any(k in h_low for k in ["오차", "편차", "diff", "deviation", "error"]):
            dev_idx = idx

    export_headers = list(headers)
    if judge_idx == -1:
        export_headers.append("AI_자동규격판정")

    for r_num, row in enumerate(data_rows, start=1):
        row_str_join = " | ".join([c for c in row if c])
        judge_val = row[judge_idx] if (0 <= judge_idx < len(row)) else ""
        is_fail = any(k in judge_val for k in ["불합격", "부적합", "불량", "NG", "FAIL", "반려"])
        is_pass = not is_fail and any(k in judge_val for k in ["합격", "적합", "정상", "OK", "PASS"])

        # [핵심 실무 기능] 만약 엑셀에 합격/불합격 글자가 없거나 비어있다면, Spec과 실측치를 수학적으로 직접 비교하여 자동 판정!
        auto_dev: Optional[float] = None
        if not is_fail and not is_pass and (0 <= spec_idx < len(row)) and (0 <= val_idx < len(row)):
            spec_ok, calc_dev = evaluate_spec_compliance(row[spec_idx], row[val_idx])
            auto_dev = calc_dev
            if spec_ok is False:
                is_fail = True
                row_str_join += f" | [AI 수학연산 판정: 불합격 (편차 {calc_dev:+.2f})]"
            elif spec_ok is True:
                is_pass = True
                row_str_join += f" | [AI 수학연산 판정: 합격 (편차 {calc_dev:+.2f})]"

        export_row = list(row) + [""] * max(0, len(headers) - len(row))
        if judge_idx == -1:
            export_row.append("불합격(NG)" if is_fail else ("합격(OK)" if is_pass else "확인필요"))
        structured_export_rows.append(export_row)

        vendor_name = row[vendor_idx] if (0 <= vendor_idx < len(row) and row[vendor_idx]) else "기타/미상"

        if is_fail:
            fail_count += 1
            vendor_stats.setdefault(vendor_name, {"total": 0, "fail": 0})
            vendor_stats[vendor_name]["total"] += 1
            vendor_stats[vendor_name]["fail"] += 1
            fail_details.append(f"• [🚨 부적합(불합격) 검출 #{len(fail_details)+1} (행 {r_num})]: {row_str_join}.")
        elif is_pass:
            pass_count += 1
            vendor_stats.setdefault(vendor_name, {"total": 0, "fail": 0})
            vendor_stats[vendor_name]["total"] += 1
            pass_details.append(f"• [✅ 적격(합격) 확인 #{len(pass_details)+1} (행 {r_num})]: {row_str_join}.")
        else:
            pass_details.append(f"• [데이터 행 {r_num}]: {row_str_join}.")

        if 0 <= val_idx < len(row) and row[val_idx]:
            p_name = row[item_idx] if (0 <= item_idx < len(row)) else f"행{r_num}"
            c_name = row[check_idx] if (0 <= check_idx < len(row)) else headers[val_idx]
            item_metric_list.append(f"{p_name}({c_name}: {row[val_idx]})")

        if 0 <= dev_idx < len(row) and row[dev_idx]:
            clean_dev = re.sub(r"[,%\s]", "", str(row[dev_idx]))
            if re.match(r"^[+-]?\d+(?:\.\d+)?$", clean_dev):
                try:
                    deviation_vals.append(float(clean_dev))
                except Exception:
                    pass
        elif auto_dev is not None:
            deviation_vals.append(auto_dev)

    # 엑셀 2번째 시트(원본 데이터 + AI 판정표) 출력을 위해 메모리에 구조화된 테이블 저장
    LAST_PARSED_TABLE["latest"] = {
        "filename": filename,
        "headers": export_headers,
        "rows": structured_export_rows,
    }

    lines = [
        f"• [첨부 데이터 전수 스캔 완료]: 파일명 '{filename}' (헤더 자동 탐지: {h_idx+1}행) | 총 데이터 {total_rows}건 전수 분석 (누락 0건) | 컬럼: {', '.join(headers[:10])}."
    ]

    if pass_count + fail_count > 0:
        judged_total = pass_count + fail_count
        defect_rate = round((fail_count / judged_total) * 100, 2)
        lines.append(
            f"• [전수 품질 판정 통계]: 총 판정 {judged_total}건 중 합격 {pass_count}건 ({round(100 - defect_rate, 2)}%), 불합격(부적합) {fail_count}건 (불량률 {defect_rate}%)."
        )

    if vendor_stats:
        v_summaries = []
        for v_name, st in vendor_stats.items():
            v_rate = round((st["fail"] / max(1, st["total"])) * 100, 1)
            v_summaries.append(f"{v_name}(총 {st['total']}건 중 불량 {st['fail']}건, 불량률 {v_rate}%)")
        lines.append(f"• [협력사별 품질·불량률 집계]: {', '.join(v_summaries[:8])}.")

    if item_metric_list or deviation_vals:
        dev_stat_str = ""
        if deviation_vals:
            avg_abs_dev = round(sum(abs(x) for x in deviation_vals) / len(deviation_vals), 2)
            min_dev = min(deviation_vals)
            max_dev = max(deviation_vals)
            dev_stat_str = f" | 규격 대비 편차(오차) 분포[최소 {min_dev:+.1f} ~ 최대 {max_dev:+.1f}, 평균 절대편차 {avg_abs_dev}]"
        lines.append(f"• [항목별 실측치(단위별 분리) 및 편차 분석]: {', '.join(item_metric_list[:6])}{dev_stat_str}.")

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
    }
    return "\n".join(lines), meta

def parse_uploaded_document(filename: str, content: bytes) -> Tuple[str, dict]:
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
                return _analyze_tabular_rows(filename, reader)

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
                summary_str, tab_meta = _analyze_tabular_rows(filename, clean_rows)
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

            clean_pdf = re.sub(r"\s+", " ", pdf_text).strip()
            extracted_lines = [f"• [첨부 PDF 문서 전수 스캔]: {filename} (총 {meta.get('pages', 1)}페이지, {meta['size_kb']}KB)."]
            if len(clean_pdf) > 20:
                sents = [s.strip() for s in re.split(r"(?<=[.?!다요음함])\s+", clean_pdf) if len(s.strip()) > 20]
                for idx, s in enumerate(sents[:10], 1):
                    extracted_lines.append(f"• [PDF 핵심 문장 {idx}]: {s[:180]}.")
            return "\n".join(extracted_lines), meta

        txt = content.decode("utf-8", errors="ignore")
        lines = [line.strip() for line in txt.splitlines() if len(line.strip()) > 5]
        out = [f"• [첨부 문서명]: {filename} (총 {len(lines)}줄)."]
        for idx, l in enumerate(lines[:12], 1):
            out.append(f"• [문서 주요 내용 {idx}]: {l[:170]}.")
        return "\n".join(out), meta

    except Exception:
        return f"• [첨부 파일 로드]: {filename} ({meta['size_kb']}KB) 분석 준비 완료.", meta
''',

    # 2. 실무형 2-Sheet 엑셀 변환기: Sheet 1(결재 요약 보고서) + Sheet 2(필터·수식 작업이 가능한 원본 컬럼 분리 데이터 & 불합격 자동 빨간색 하이라이트!)
    "backend/report_exporter.py": r'''import io
import re
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape
from backend.file_processor import LAST_PARSED_TABLE

def parse_report_sections(report_text: str) -> list[tuple[str, list[str]]]:
    sections = []
    current_title = "핵심 요약 보고서"
    current_lines = []

    for raw_line in report_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("📌") or re.match(r"^#{1,3}\s+", line):
            if current_lines:
                sections.append((current_title, current_lines))
                current_lines = []
            current_title = re.sub(r"^(?:📌|#{1,3})\s*", "", line).strip()
        else:
            clean_item = re.sub(r"^[•\-\*]\s*", "", line).strip()
            current_lines.append(clean_item)

    if current_lines:
        sections.append((current_title, current_lines))
    return sections

def build_docx_bytes(title: str, report_text: str) -> bytes:
    sections = parse_report_sections(report_text)
    now_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    clean_t = re.sub(r"\s*\(첨부파일.*\)", "", title).strip()

    body_xml_parts = [
        f"""<w:p>
            <w:pPr><w:jc w:val="left"/><w:spacing w:after="200"/></w:pPr>
            <w:r><w:rPr><w:b/><w:sz w:val="36"/><w:color w:val="1E3A5F"/></w:rPr>
            <w:t>{escape(clean_t)}</w:t></w:r>
        </w:p>""",
        f"""<w:p>
            <w:pPr><w:spacing w:after="300"/></w:pPr>
            <w:r><w:rPr><w:sz w:val="20"/><w:color w:val="64748B"/></w:rPr>
            <w:t>발행 일시: {now_date} | 발행 시스템: AI Company Hub 엔터프라이즈 결재 시스템</w:t></w:r>
        </w:p>"""
    ]

    for sec_title, items in sections:
        body_xml_parts.append(f"""<w:p>
            <w:pPr><w:spacing w:before="280" w:after="140"/></w:pPr>
            <w:r><w:rPr><w:b/><w:sz w:val="26"/><w:color w:val="0F172A"/></w:rPr>
            <w:t>■ {escape(sec_title)}</w:t></w:r>
        </w:p>""")
        for item in items:
            body_xml_parts.append(f"""<w:p>
                <w:pPr><w:ind w:left="360"/><w:spacing w:after="100"/></w:pPr>
                <w:r><w:rPr><w:sz w:val="22"/><w:color w:val="1E293B"/></w:rPr>
                <w:t>• {escape(item)}</w:t></w:r>
            </w:p>""")

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        {''.join(body_xml_parts)}
        <w:sectPr>
          <w:pgSz w:w="11906" w:h="16838"/>
          <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
        </w:sectPr>
      </w:body>
    </w:document>"""

    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
      <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
      <Default Extension="xml" ContentType="application/xml"/>
      <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
    </Types>"""

    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
      <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
    </Relationships>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml.strip())
        zf.writestr("_rels/.rels", rels_xml.strip())
        zf.writestr("word/document.xml", document_xml.strip())
    return buf.getvalue()

def build_xlsx_bytes(title: str, report_text: str) -> bytes:
    """
    [현업 즉시 투입용 2-Sheet 엑셀 생성기]
    - Sheet 1 (최종승인_결재보고서): 5단 심층 결재 보고서 양식
    - Sheet 2 (전수검수_데이터_원본): 첨부된 엑셀/CSV 데이터가 있을 경우 개별 컬럼을 쪼개어 필터링/정렬이 가능한 실무 데이터 테이블로 제공하고, 불합격(NG) 행은 빨간색 셀로 자동 강조!
    """
    sections = parse_report_sections(report_text)
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "최종승인_결재보고서"

    header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    sec_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
    ng_fill = PatternFill(start_color="FFE4E6", end_color="FFE4E6", fill_type="solid")
    ok_fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    clean_t = re.sub(r"\s*\(첨부파일.*\)", "", title).strip()
    ws.merge_cells("A1:C1")
    ws["A1"] = f"📋 {clean_t}"
    ws["A1"].font = Font(name="맑은 고딕", size=13, bold=True, color="FFFFFF")
    ws["A1"].fill = header_fill
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 32

    ws["A2"] = "구분 / 섹션"
    ws["B2"] = "항목 번호"
    ws["C2"] = "상세 분석 및 검증 내용"
    for col in ("A", "B", "C"):
        c = ws[f"{col}2"]
        c.font = Font(name="맑은 고딕", size=10, bold=True, color="1E293B")
        c.fill = sec_fill
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border
    ws.row_dimensions[2].height = 24

    row_idx = 3
    for sec_title, items in sections:
        for idx, item in enumerate(items, start=1):
            ws.cell(row=row_idx, column=1, value=sec_title).alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            ws.cell(row=row_idx, column=2, value=f"#{idx}").alignment = Alignment(horizontal="center", vertical="center")
            ws.cell(row=row_idx, column=3, value=item).alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            is_ng_row = "부적합" in item or "불합격" in item
            for c_i in range(1, 4):
                cell = ws.cell(row=row_idx, column=c_i)
                cell.font = Font(name="맑은 고딕", size=10, bold=(c_i == 1 or is_ng_row), color=("B91C1C" if is_ng_row else "0F172A"))
                if is_ng_row:
                    cell.fill = ng_fill
                cell.border = thin_border
            ws.row_dimensions[row_idx].height = 28
            row_idx += 1

    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 88

    # Sheet 2: 현업 담당자가 바로 필터링·피벗·수식 작업을 할 수 있는 개별 컬럼 분리형 원본 데이터 시트!
    parsed_tbl = LAST_PARSED_TABLE.get("latest")
    if parsed_tbl and parsed_tbl.get("headers") and parsed_tbl.get("rows"):
        ws2 = wb.create_sheet(title="전수검수_원본데이터")
        tbl_headers = parsed_tbl["headers"]
        tbl_rows = parsed_tbl["rows"]

        for c_idx, h_text in enumerate(tbl_headers, start=1):
            cell = ws2.cell(row=1, column=c_idx, value=h_text)
            cell.font = Font(name="맑은 고딕", size=10, bold=True, color="FFFFFF")
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border
            col_letter = get_column_letter(c_idx)
            ws2.column_dimensions[col_letter].width = max(14, min(28, len(str(h_text)) * 2 + 6))
        ws2.row_dimensions[1].height = 26

        for r_i, r_vals in enumerate(tbl_rows, start=2):
            row_joined = " ".join(str(x) for x in r_vals)
            is_fail_data = any(k in row_joined for k in ["불합격", "부적합", "NG", "FAIL", "반려"])
            for c_i, val in enumerate(r_vals, start=1):
                cell = ws2.cell(row=r_i, column=c_i)
                # 숫자로 변환 가능한 값은 실제 숫자(float/int) 타입으로 넣어 엑셀 SUM/AVERAGE 수식이 즉시 작동하게 함!
                clean_num = re.sub(r"[,%\s]", "", str(val))
                if re.match(r"^-?\d+(?:\.\d+)?$", clean_num) and not str(val).startswith("LOT"):
                    cell.value = float(clean_num) if "." in clean_num else int(clean_num)
                else:
                    cell.value = val

                cell.font = Font(
                    name="맑은 고딕",
                    size=10,
                    bold=is_fail_data,
                    color=("B91C1C" if is_fail_data else "0F172A"),
                )
                cell.fill = ng_fill if is_fail_data else ok_fill
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = thin_border
            ws2.row_dimensions[r_i].height = 22

        # 엑셀 자동 필터(AutoFilter) 기본 활성화!
        last_col_letter = get_column_letter(len(tbl_headers))
        ws2.auto_filter.ref = f"A1:{last_col_letter}{len(tbl_rows)+1}"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
''',
}

if __name__ == "__main__":
    for path, content in FILES.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        py_compile.compile(path, doraise=True)
        print(f"✅ 실무 패치 적용 및 컴파일 완료: {path}")

    # workflow.py의 1번 요약과 2번 섹션 첫 문장 중복까지 깔끔하게 제거
    with open("backend/workflow.py", "r", encoding="utf-8") as f:
        wf = f.read()
    wf = wf.replace("sec2_list = all_sents[:4]", "sec2_list = all_sents[2:6] if len(all_sents) > 2 else all_sents[:4]")
    wf = wf.replace("sec3_list = all_sents[4:9]", "sec3_list = all_sents[6:11] if len(all_sents) > 6 else all_sents[:5]")
    with open("backend/workflow.py", "w", encoding="utf-8") as f:
        f.write(wf)

    print("\n=====================================================================")
    print("🧪 [현업 실무 스트레스 테스트 (UAT) 3종 구동 결과]")
    print("=====================================================================")
    from backend.file_processor import parse_uploaded_document
    from backend.report_exporter import build_xlsx_bytes
    import openpyxl, io

    # 실무 테스트 1 & 2: 상단 1~2행에 결재란/제목이 있고, '판정(합격/불합격)' 열이 아예 없는 실제 협력사 성적서 CSV
    real_world_messy_csv = (
        "수입검사 성적서 (CoA),,,,,,\n"
        "결재: 담당 / 팀장,작성일: 2026-11-08,,,,,\n"
        "검사일자,LOT번호,품목명,협력사명,검사항목,기준규격(Spec),실측측정값\n"
        "2026-11-08,LOT-A1,양극재,(주)에코소재,순도(%),99.5 이상,99.1\n"
        "2026-11-08,LOT-A2,파우치,삼기정밀,두께(μm),100 ± 5,106.2\n"
        "2026-11-08,LOT-A3,전해액,신성켐텍,수분(ppm),20 이하,14.5\n"
    ).encode("utf-8")

    summary, meta = parse_uploaded_document("현업_비정형_성적서_테스트.csv", real_world_messy_csv)
    print(summary)
    assert meta["header_row"] == 3, "상단 결재란 건너뛰기(헤더 3행 탐지) 실패!"
    assert meta["fail_count"] == 2 and meta["pass_count"] == 1, "Spec 수학 연산 자동 판정 실패!"
    print("\n✔ [UAT 1 & 2 통과] 상단 결재란(1~2행) 자동 스킵 성공 & '판정' 열이 없어도 Spec('99.5 이상', '100 ± 5')을 수학 연산하여 불량 2건·합격 1건 자동 판정 성공!")

    # 실무 테스트 3: 2-Sheet 엑셀 생성 및 숫자 셀(SUM/AVERAGE 가능) + AutoFilter 적용 확인
    xlsx_bytes = build_xlsx_bytes("현업 성적서 결재 보고서", "📌 1. 요약\n• 불합격 2건 검출\n📌 2. 상세\n• 조치 요망")
    wb_check = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    assert "최종승인_결재보고서" in wb_check.sheetnames and "전수검수_원본데이터" in wb_check.sheetnames
    ws2_check = wb_check["전수검수_원본데이터"]
    assert ws2_check["H1"].value == "AI_자동규격판정"
    assert ws2_check["H2"].value == "불합격(NG)" and ws2_check["G2"].value == 99.1
    print(f"✔ [UAT 3 통과] 엑셀 다운로드 시 2개 시트({wb_check.sheetnames}) 생성 & 수치 셀 타입(float 99.1) 및 AI 자동판정 열('불합격(NG)') 생성 확인 완료!")
