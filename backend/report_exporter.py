import io
import re
import uuid
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape
from backend.db_store import get_session_table

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

def build_docx_bytes(title: str, report_text: str, session_id: str = "default") -> bytes:
    sections = parse_report_sections(report_text)
    now_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    trace_id = f"DOC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
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
            <w:t>문서추적번호: {trace_id} | 발행일시: {now_date} | 발행처: AI Company Hub 결재시스템</w:t></w:r>
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

def build_xlsx_bytes(title: str, report_text: str, session_id: str = "default") -> bytes:
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

    trace_id = f"DOC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    clean_t = re.sub(r"\s*\(첨부파일.*\)", "", title).strip()
    ws.merge_cells("A1:C1")
    ws["A1"] = f"📋 [{trace_id}] {clean_t}"
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

    # 세션별로 안전하게 격리된 테이블 데이터(get_session_table)만 가져와 Sheet 2 생성!
    parsed_tbl = get_session_table(session_id)
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

        last_col_letter = get_column_letter(len(tbl_headers))
        ws2.auto_filter.ref = f"A1:{last_col_letter}{len(tbl_rows)+1}"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
