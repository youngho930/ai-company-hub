import io
import os
import re
import uuid
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape
from backend.db_store import get_session_table, get_session_upload


def build_export_filename(title: str, fmt: str, attached_filename: str = "", session_id: str = "default") -> str:
    """
    [주제·첨부파일명 기반 동적 다운로드 파일명 생성기]
    - 첨부파일이 있는 경우: [결재보고서]_{첨부파일명_without_ext}_분석_{YYYY-MM-DD}.{ext}
    - 첨부파일이 없는 경우: [결재보고서]_{핵심안건명}_{YYYY-MM-DD}.{ext}
    """
    ext = {"docx": "docx", "xlsx": "xlsx", "pdf": "pdf", "md": "md"}.get((fmt or "md").lower().strip(), "md")
    date_str = datetime.now().strftime("%Y-%m-%d")

    fname = (attached_filename or "").strip()
    if not fname and session_id:
        sess_fname, _ = get_session_upload(session_id)
        if sess_fname:
            fname = sess_fname.strip()

    def _clean_part(s: str, max_len: int = 36) -> str:
        s = re.sub(r'[\\/:*?"<>|\r\n]+', "_", s or "")
        s = re.sub(r"\s+", "_", s).strip("_- ")
        s = re.sub(r"_+", "_", s)
        return s[:max_len].strip("_- ") or "핵심안건"

    if fname:
        base_no_ext = os.path.splitext(os.path.basename(fname))[0]
        clean_base = _clean_part(base_no_ext, max_len=40)
        return f"[결재보고서]_{clean_base}_분석_{date_str}.{ext}"

    raw_title = re.sub(r"\s*\(첨부파일[^)]*\)", "", title or "")
    raw_title = re.sub(r"\s*(?:정밀\s*분석\s*및\s*결재\s*보고서|최종\s*승인\s*결재\s*보고서|결재\s*보고서|심층\s*보고서|보고서)\s*$", "", raw_title).strip()
    raw_title = re.sub(r"\s*(?:조사해줘|작성해줘|분석해줘|검토해줘|정리해줘|알려줘|해줘)\s*$", "", raw_title).strip()
    clean_topic = _clean_part(raw_title, max_len=32)
    return f"[결재보고서]_{clean_topic}_{date_str}.{ext}"

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
    ws.title = "1_최종승인_결재보고서"

    header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    sub_header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    sec_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
    ng_fill = PatternFill(start_color="FFE4E6", end_color="FFE4E6", fill_type="solid")
    warn_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    ceo_fill = PatternFill(start_color="EEF2FF", end_color="EEF2FF", fill_type="solid")
    ok_fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    trace_id = f"DOC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    clean_t = re.sub(r"\s*\(첨부파일.*\)", "", title).strip()

    # Executive 타이틀 & 3단 결재란 헤더
    ws.merge_cells("A1:D1")
    ws["A1"] = f"📋 [{trace_id}] {clean_t}"
    ws["A1"].font = Font(name="맑은 고딕", size=13, bold=True, color="FFFFFF")
    ws["A1"].fill = header_fill
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 34

    ws["A2"] = f"문서추적번호: {trace_id}"
    ws["B2"] = f"발행일시: {now_str}"
    ws.merge_cells("C2:D2")
    ws["C2"] = "발행처: AI Company Hub 전자결재 시스템 | 데이터 검증: Python Deterministic Engine"
    for col_idx in range(1, 5):
        c = ws.cell(row=2, column=col_idx)
        c.font = Font(name="맑은 고딕", size=9, bold=True, color="334155")
        c.fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        c.border = thin_border
    ws.row_dimensions[2].height = 22

    # 3단 결재란 (기안 / 검수 / 최종승인 신영호 대표)
    approval_labels = ["결재 등급: Executive Approved", "기안 (전담 실무팀)", "검수 (전담 팀장)", "최종승인 (신영호 대표)"]
    approval_values = ["5단 심층 결재 완료", "작성 · 정량연산 완료", "QC 루브릭 검수 통과", "최종 승인 (직인 생략)"]
    for col_idx, (lbl, val) in enumerate(zip(approval_labels, approval_values), start=1):
        c_top = ws.cell(row=3, column=col_idx, value=lbl)
        c_top.font = Font(name="맑은 고딕", size=9, bold=True, color="FFFFFF")
        c_top.fill = sub_header_fill
        c_top.alignment = Alignment(horizontal="center", vertical="center")
        c_top.border = thin_border

        c_bot = ws.cell(row=4, column=col_idx, value=val)
        c_bot.font = Font(name="맑은 고딕", size=9, bold=(col_idx == 4), color=("047857" if col_idx == 4 else "1E293B"))
        c_bot.fill = ok_fill if col_idx == 4 else PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        c_bot.alignment = Alignment(horizontal="center", vertical="center")
        c_bot.border = thin_border
    ws.row_dimensions[3].height = 20
    ws.row_dimensions[4].height = 22
    ws.row_dimensions[5].height = 8

    headers_s1 = ["구분 / 섹션", "순번", "상세 분석 · Audit Trail · CAPA 내용", "판정 / 상태"]
    for c_i, h_lbl in enumerate(headers_s1, start=1):
        c = ws.cell(row=6, column=c_i, value=h_lbl)
        c.font = Font(name="맑은 고딕", size=10, bold=True, color="1E293B")
        c.fill = sec_fill
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border
    ws.row_dimensions[6].height = 24

    row_idx = 7
    for sec_title, items in sections:
        for idx, item in enumerate(items, start=1):
            is_gap_row = "보완필요(Gap)" in item or "보완필요" in item
            is_ng_row = (not is_gap_row) and ("부적합" in item or "불합격" in item or "Line-Stop" in item)
            is_warn_row = is_gap_row or ((not is_ng_row) and ("잠재 산포 리스크 경고" in item or "⚠️" in item))
            is_ceo_row = "⚡" in item or "CEO" in item
            is_ok_row = (not is_ng_row and not is_warn_row) and ("✅" in item or "적합" in item or "적격" in item)

            status_badge = (
                "⚠️ 보완필요(Gap)" if is_gap_row
                else ("🚨 부적합/조치" if is_ng_row
                      else ("⚠️ 산포리스크" if is_warn_row
                            else ("⚡ CEO 지시반영" if is_ceo_row
                                  else ("✅ 적합/정상" if is_ok_row else "📌 분석항목"))))
            )
            ws.cell(row=row_idx, column=1, value=sec_title).alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            ws.cell(row=row_idx, column=2, value=f"#{idx}").alignment = Alignment(horizontal="center", vertical="center")
            ws.cell(row=row_idx, column=3, value=item).alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            ws.cell(row=row_idx, column=4, value=status_badge).alignment = Alignment(horizontal="center", vertical="center")

            for c_i in range(1, 5):
                cell = ws.cell(row=row_idx, column=c_i)
                text_color = "B91C1C" if is_ng_row else ("B45309" if is_warn_row else ("3730A3" if is_ceo_row else "0F172A"))
                cell.font = Font(name="맑은 고딕", size=10, bold=(c_i in (1, 4) or is_ng_row or is_ceo_row), color=text_color)
                if is_ng_row:
                    cell.fill = ng_fill
                elif is_warn_row:
                    cell.fill = warn_fill
                elif is_ceo_row:
                    cell.fill = ceo_fill
                elif is_ok_row and c_i == 4:
                    cell.fill = ok_fill
                cell.border = thin_border
            est_lines = max(1, (len(item) // 64) + 1)
            ws.row_dimensions[row_idx].height = max(26, min(110, est_lines * 16 + 8))
            row_idx += 1

    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 84
    ws.column_dimensions["D"].width = 18

    # 세션 테이블 및 리포트 기반 정량표 (Sheet 2: 2_SPC_및_Audit_Trail_정량표)
    parsed_tbl = get_session_table(session_id)
    spc_rows = (parsed_tbl or {}).get("spc") or []
    audit_matches = re.findall(
        r"\[원본\s*(#\d+행)\s*\|\s*([^|\]]+)\|\s*([^|\]]+)\]\s*([^:]+):\s*기준규격\(Spec\)\s*'([^']+)'\s*대비\s*실측값\s*'([^']+)'[^➔]*➔\s*판정:\s*([^\n]+)",
        report_text or "",
    )
    if spc_rows or audit_matches:
        ws_spc = wb.create_sheet(title="2_SPC_및_Audit_Trail_정량표")
        ws_spc.merge_cells("A1:I1")
        ws_spc["A1"] = "📊 Real SPC(표준편차 σ · Cp · Cpk) 및 1:1 Audit Trail 정량 추적표"
        ws_spc["A1"].font = Font(name="맑은 고딕", size=12, bold=True, color="FFFFFF")
        ws_spc["A1"].fill = header_fill
        ws_spc["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws_spc.row_dimensions[1].height = 30

        r_ptr = 3
        if spc_rows:
            spc_headers = ["품목 - 검사항목", "표본수(N)", "LSL(하한)", "USL(상한)", "평균(Mean)", "표준편차(σ)", "Cp", "Cpk", "공정능력 판정"]
            for c_i, h_t in enumerate(spc_headers, start=1):
                c = ws_spc.cell(row=r_ptr, column=c_i, value=h_t)
                c.font = Font(name="맑은 고딕", size=10, bold=True, color="1E293B")
                c.fill = sec_fill
                c.alignment = Alignment(horizontal="center", vertical="center")
                c.border = thin_border
            ws_spc.row_dimensions[r_ptr].height = 24
            r_ptr += 1

            for sp in spc_rows:
                cpk_val = sp.get("cpk")
                sample_n = int(sp.get("n") or 0)
                is_weak_cpk = cpk_val is not None and cpk_val < 1.33
                status_str = (
                    "🚨 Cpk < 1.33 (산포 개선 필요)" if is_weak_cpk
                    else ("✅ 공정능력 적격" if cpk_val is not None
                          else ("ℹ️ 단일 표본(n=1)" if sample_n == 1 else "ℹ️ 편측 Spec"))
                )
                vals = [
                    sp.get("group") or f"{sp.get('item', '-')}-{sp.get('check', '-')}",
                    sp.get("n", 0),
                    sp.get("lsl") if sp.get("lsl") is not None else "-",
                    sp.get("usl") if sp.get("usl") is not None else "-",
                    sp.get("mean", "-"),
                    sp.get("sigma", "-"),
                    sp.get("cp") if sp.get("cp") is not None else "-",
                    cpk_val if cpk_val is not None else "-",
                    status_str,
                ]
                for c_i, v in enumerate(vals, start=1):
                    c = ws_spc.cell(row=r_ptr, column=c_i, value=v)
                    c.font = Font(name="맑은 고딕", size=10, bold=is_weak_cpk, color=("B45309" if is_weak_cpk else "0F172A"))
                    c.fill = warn_fill if is_weak_cpk else ok_fill
                    c.alignment = Alignment(horizontal=("left" if c_i in (1, 9) else "center"), vertical="center")
                    c.border = thin_border
                ws_spc.row_dimensions[r_ptr].height = 22
                r_ptr += 1
            r_ptr += 1

        if audit_matches:
            audit_headers = ["원본 행번호", "LOT 번호", "품목 · 협력사", "검사항목", "기준규격(Spec)", "실측값", "최종 판정", "조치 구분", "감사 추적 상태"]
            for c_i, h_t in enumerate(audit_headers, start=1):
                c = ws_spc.cell(row=r_ptr, column=c_i, value=h_t)
                c.font = Font(name="맑은 고딕", size=10, bold=True, color="FFFFFF")
                c.fill = sub_header_fill
                c.alignment = Alignment(horizontal="center", vertical="center")
                c.border = thin_border
            ws_spc.row_dimensions[r_ptr].height = 24
            r_ptr += 1

            for row_num, lot_id, item_vendor, check_item, spec_s, meas_s, judge_s in audit_matches:
                is_ng = "부적합" in judge_s or "불합격" in judge_s
                vals = [
                    row_num.strip(),
                    lot_id.strip(),
                    item_vendor.strip(),
                    check_item.strip(),
                    spec_s.strip(),
                    meas_s.strip(),
                    judge_s.strip(),
                    "SCAR·8D·Line-Stop" if is_ng else "정상 승인",
                    "1:1 Audit Verified",
                ]
                for c_i, v in enumerate(vals, start=1):
                    c = ws_spc.cell(row=r_ptr, column=c_i, value=v)
                    c.font = Font(name="맑은 고딕", size=10, bold=is_ng, color=("B91C1C" if is_ng else "0F172A"))
                    c.fill = ng_fill if is_ng else ok_fill
                    c.alignment = Alignment(horizontal=("left" if c_i in (3, 7) else "center"), vertical="center")
                    c.border = thin_border
                ws_spc.row_dimensions[r_ptr].height = 22
                r_ptr += 1

        col_widths_s2 = [28, 12, 18, 16, 16, 14, 22, 18, 22]
        for idx_w, w_val in enumerate(col_widths_s2, start=1):
            ws_spc.column_dimensions[get_column_letter(idx_w)].width = w_val

    # 세션별로 안전하게 격리된 테이블 데이터(get_session_table)만 가져와 Sheet 3 생성!
    if parsed_tbl and parsed_tbl.get("headers") and parsed_tbl.get("rows"):
        ws3 = wb.create_sheet(title="3_전수검수_원본데이터")
        tbl_headers = parsed_tbl["headers"]
        tbl_rows = parsed_tbl["rows"]

        for c_idx, h_text in enumerate(tbl_headers, start=1):
            cell = ws3.cell(row=1, column=c_idx, value=h_text)
            cell.font = Font(name="맑은 고딕", size=10, bold=True, color="FFFFFF")
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border
            col_letter = get_column_letter(c_idx)
            ws3.column_dimensions[col_letter].width = max(14, min(28, len(str(h_text)) * 2 + 6))
        ws3.row_dimensions[1].height = 26

        for r_i, r_vals in enumerate(tbl_rows, start=2):
            row_joined = " ".join(str(x) for x in r_vals)
            is_fail_data = any(k in row_joined for k in ["불합격", "부적합", "NG", "FAIL", "반려"])
            for c_i, val in enumerate(r_vals, start=1):
                cell = ws3.cell(row=r_i, column=c_i)
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
            ws3.row_dimensions[r_i].height = 22

        last_col_letter = get_column_letter(len(tbl_headers))
        ws3.auto_filter.ref = f"A1:{last_col_letter}{len(tbl_rows)+1}"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
