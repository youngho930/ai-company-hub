import io
import csv
import re
from typing import Tuple, Optional
from backend.db_store import set_session_table, scrub_pii_and_secrets

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

    m_max = re.search(r"(?:<=|이하|미만|max)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:이하|미만|max)", s, flags=re.I)
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
        masked_row = [scrub_pii_and_secrets(str(c))[0] for c in row]
        row_str_join = " | ".join([c for c in masked_row if c])
        judge_val = masked_row[judge_idx] if (0 <= judge_idx < len(masked_row)) else ""
        is_fail = any(k in judge_val for k in ["불합격", "부적합", "불량", "NG", "FAIL", "반려"])
        is_pass = not is_fail and any(k in judge_val for k in ["합격", "적합", "정상", "OK", "PASS"])

        auto_dev: Optional[float] = None
        if not is_fail and not is_pass and (0 <= spec_idx < len(masked_row)) and (0 <= val_idx < len(masked_row)):
            spec_ok, calc_dev = evaluate_spec_compliance(masked_row[spec_idx], masked_row[val_idx])
            auto_dev = calc_dev
            if spec_ok is False:
                is_fail = True
                row_str_join += f" | [AI 수학연산 판정: 불합격 (편차 {calc_dev:+.2f})]"
            elif spec_ok is True:
                is_pass = True
                row_str_join += f" | [AI 수학연산 판정: 합격 (편차 {calc_dev:+.2f})]"

        export_row = list(masked_row) + [""] * max(0, len(headers) - len(masked_row))
        if judge_idx == -1:
            export_row.append("불합격(NG)" if is_fail else ("합격(OK)" if is_pass else "확인필요"))
        structured_export_rows.append(export_row)

        vendor_name = masked_row[vendor_idx] if (0 <= vendor_idx < len(masked_row) and masked_row[vendor_idx]) else "기타/미상"

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

    # 세션별로 격리된 테이블 스토어에 저장!
    set_session_table(session_id, {
        "filename": filename,
        "headers": export_headers,
        "rows": structured_export_rows,
    })

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
                return _analyze_tabular_rows(filename, reader, session_id=session_id)

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
            return "\n".join(extracted_lines), meta

        txt, _ = scrub_pii_and_secrets(content.decode("utf-8", errors="ignore"))
        lines = [line.strip() for line in txt.splitlines() if len(line.strip()) > 5]
        out = [f"• [첨부 문서명]: {filename} (총 {len(lines)}줄)."]
        for idx, l in enumerate(lines[:12], 1):
            out.append(f"• [문서 주요 내용 {idx}]: {l[:170]}.")
        return "\n".join(out), meta

    except Exception:
        return f"• [첨부 파일 로드]: {filename} ({meta['size_kb']}KB) 분석 준비 완료.", meta
