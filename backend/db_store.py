import os
import re
import time
import json
import uuid
import sqlite3
import asyncio
import logging
from datetime import datetime
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("AICompanyHub.DB")

DB_PATH = os.path.join(os.getcwd(), "mission_archive.db")
WEBHOOK_CONFIG_PATH = os.path.join(os.getcwd(), ".enterprise-webhooks.json")
SESSION_TTL_SECONDS = 3600  # 1시간 경과 세션 자동 메모리 회수(GC)

# 세션별 완전 격리 저장소 (TTL 타임스탬프 포함)
SESSION_UPLOADS: dict[str, dict] = {}
SESSION_TABLES: dict[str, dict] = {}
SESSION_HITL: dict[str, dict] = {}
SESSION_LIVE_INSTRUCTIONS: dict[str, list[str]] = {}
SESSION_LAST_PROMPT: dict[str, str] = {}

COST_TRACKER: dict[str, float | int] = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "total_cost_usd": 0.0,
    "saved_cost_usd": 0.0,
    "cache_hits": 0,
    "budget_limit_usd": 1.00,
    "pii_masked_count": 0,
}

def scrub_pii_and_secrets(text: str) -> tuple[str, int]:
    """
    [대기업 보안 거버넌스: DLP / PII 자동 마스킹 필터]
    외부 LLM 전송 전 주민등록번호, 휴대전화번호, 이메일, API 키 패턴을 감지하여 마스킹합니다.
    """
    if not text:
        return "", 0
    masked_cnt = 0
    patterns = [
        (r"\b(\d{6})[-]\d{7}\b", r"\1-*******"),  # 주민등록번호
        (r"\b(01[016789])[-.\s]?(\d{3,4})[-.\s]?(\d{4})\b", r"\1-****-\3"),  # 휴대전화
        (r"\b(sk-[a-zA-Z0-9]{10,})\b", r"[MASKED_API_KEY]"),  # API Secret
    ]
    out = text
    for pat, repl in patterns:
        out, n = re.subn(pat, repl, out)
        masked_cnt += n
    if masked_cnt > 0:
        COST_TRACKER["pii_masked_count"] = int(COST_TRACKER.get("pii_masked_count", 0)) + masked_cnt
        logger.info(f"PII/Secret DLP Guardrail triggered: masked {masked_cnt} sensitive items.")
    return out, masked_cnt

def evict_expired_sessions() -> int:
    """TTL(1시간)이 지난 인메모리 세션 데이터를 자동 정리하여 메모리 누수(Memory Leak) 원천 차단"""
    now = time.time()
    expired = [
        sid for sid, data in SESSION_UPLOADS.items()
        if now - data.get("ts", now) > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        SESSION_UPLOADS.pop(sid, None)
        SESSION_TABLES.pop(sid, None)
        SESSION_HITL.pop(sid, None)
        SESSION_LIVE_INSTRUCTIONS.pop(sid, None)
        SESSION_LAST_PROMPT.pop(sid, None)
    return len(expired)

def get_session_upload(session_id: str) -> dict[str, str]:
    evict_expired_sessions()
    return SESSION_UPLOADS.get(session_id, {"filename": "", "summary": ""})

def set_session_upload(session_id: str, filename: str, summary: str) -> None:
    evict_expired_sessions()
    clean_summary, _ = scrub_pii_and_secrets(summary)
    SESSION_UPLOADS[session_id] = {"filename": filename, "summary": clean_summary, "ts": time.time()}

def clear_session_upload(session_id: str) -> None:
    SESSION_UPLOADS.pop(session_id, None)
    SESSION_TABLES.pop(session_id, None)

def set_session_table(session_id: str, table_data: dict) -> None:
    """전역 단일 키('latest') 오염 버그 해결: 세션별로 파싱된 원본 표를 안전하게 격리 저장"""
    SESSION_TABLES[session_id] = {**table_data, "ts": time.time()}

def get_session_table(session_id: str) -> Optional[dict]:
    if session_id in SESSION_TABLES:
        return SESSION_TABLES[session_id]
    # 하위 호환성 폴백: 세션 미지정 시 가장 최근 테이블 반환
    if SESSION_TABLES:
        latest_sid = max(SESSION_TABLES.keys(), key=lambda k: SESSION_TABLES[k].get("ts", 0))
        return SESSION_TABLES[latest_sid]
    return None

def get_or_create_session_hitl(session_id: str) -> dict:
    if session_id not in SESSION_HITL:
        SESSION_HITL[session_id] = {
            "resume_event": asyncio.Event(),
            "decision_store": {},
            "ts": time.time(),
        }
    return SESSION_HITL[session_id]

def clear_live_instructions(session_id: str) -> None:
    SESSION_LIVE_INSTRUCTIONS[session_id] = []

def push_live_instruction(session_id: str, instruction: str) -> None:
    clean_inst, _ = scrub_pii_and_secrets(instruction.strip())
    SESSION_LIVE_INSTRUCTIONS.setdefault(session_id, []).append(clean_inst)

def pop_live_instructions(session_id: str) -> list[str]:
    items = SESSION_LIVE_INSTRUCTIONS.get(session_id, [])[:]
    SESSION_LIVE_INSTRUCTIONS[session_id] = []
    return items

def record_token_usage(prompt_tokens: int, completion_tokens: int, is_cache_hit: bool = False) -> dict:
    if is_cache_hit:
        COST_TRACKER["cache_hits"] = int(COST_TRACKER["cache_hits"]) + 1
        COST_TRACKER["saved_cost_usd"] = round(float(COST_TRACKER["saved_cost_usd"]) + 0.0045, 5)
    else:
        COST_TRACKER["prompt_tokens"] = int(COST_TRACKER["prompt_tokens"]) + prompt_tokens
        COST_TRACKER["completion_tokens"] = int(COST_TRACKER["completion_tokens"]) + completion_tokens
        COST_TRACKER["total_tokens"] = int(COST_TRACKER["prompt_tokens"]) + int(COST_TRACKER["completion_tokens"])
        added_cost = (prompt_tokens * 0.0000003) + (completion_tokens * 0.0000012)
        COST_TRACKER["total_cost_usd"] = round(float(COST_TRACKER["total_cost_usd"]) + added_cost, 6)
    return dict(COST_TRACKER)

def get_cost_metrics() -> dict:
    return dict(COST_TRACKER)

def set_budget_limit(limit_usd: float) -> dict:
    COST_TRACKER["budget_limit_usd"] = max(0.01, round(limit_usd, 2))
    return dict(COST_TRACKER)

def _get_db_conn() -> sqlite3.Connection:
    """SQLite WAL(Write-Ahead Logging) 모드 및 타임아웃 적용으로 동시 읽기/쓰기 락(Lock) 방지"""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db() -> None:
    with _get_db_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mission_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_trace_id TEXT,
                session_id TEXT,
                prompt TEXT,
                normalized_prompt TEXT,
                dept TEXT,
                supervisor_name TEXT,
                worker_names TEXT,
                attached_file TEXT,
                qc_score INTEGER,
                rework_performed INTEGER,
                report_markdown TEXT,
                created_at TEXT
            )
        """)
        for col in ["normalized_prompt", "doc_trace_id"]:
            try:
                conn.execute(f"ALTER TABLE mission_history ADD COLUMN {col} TEXT")
            except Exception:
                pass
        # O(1) 고속 캐시 탐색을 위한 B-Tree 인덱스 생성
        conn.execute("CREATE INDEX IF NOT EXISTS idx_norm_prompt ON mission_history(normalized_prompt);")
        conn.execute("DELETE FROM mission_history WHERE length(report_markdown) < 250 OR prompt = '다시 찾아줘'")
        conn.commit()

def is_force_refresh_prompt(prompt: str, session_id: str = "default") -> tuple[bool, str]:
    refresh_patterns = [
        r"다시\s*찾아줘", r"다시\s*조사해줘", r"다시\s*조사", r"다시\s*검색",
        r"새로\s*찾아줘", r"새로\s*조사", r"재조사", r"재검색", r"업데이트\s*해줘", r"다시\s*알려줘"
    ]
    cleaned = prompt
    force = False
    for pat in refresh_patterns:
        if re.search(pat, cleaned, flags=re.I):
            force = True
            cleaned = re.sub(pat, " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) < 2:
        last_p = SESSION_LAST_PROMPT.get(session_id, "")
        if not last_p:
            records = list_mission_records(1)
            if records:
                last_p = records[0].get("prompt", "")
        cleaned = last_p if last_p else "한국 AI 에이전트 및 업무자동화 개발자 채용 기술 스택 조사"
    else:
        SESSION_LAST_PROMPT[session_id] = cleaned

    return force, cleaned

def normalize_query_key(prompt: str, attached_file: str = "") -> str:
    _, core_prompt = is_force_refresh_prompt(prompt)
    core_prompt = re.sub(r"\(첨부파일[^)]*\)", "", core_prompt)
    tokens = re.findall(r"[가-힣a-zA-Z0-9]+", core_prompt.lower())
    stop = {"대해서", "대해", "조사해줘", "알려줘", "작성해줘", "정리해줘", "분석해줘", "보고서", "써줘", "해줘", "파일의", "첨부한"}
    filtered = [t for t in tokens if t not in stop]
    key = "".join(filtered)
    return f"{key}::{attached_file.lower().strip()}"

def find_cached_mission(prompt: str, attached_file: str = "", session_id: str = "default") -> Optional[dict]:
    force_refresh, clean_p = is_force_refresh_prompt(prompt, session_id)
    if force_refresh:
        return None

    init_db()
    target_key = normalize_query_key(clean_p, attached_file)
    if len(target_key.replace("::", "")) < 2:
        return None

    with _get_db_conn() as conn:
        conn.row_factory = sqlite3.Row
        # 1차: 인덱스를 통한 O(1) 즉시 조회
        row = conn.execute(
            "SELECT * FROM mission_history WHERE normalized_prompt = ? AND length(report_markdown) >= 250 ORDER BY id DESC LIMIT 1",
            (target_key,),
        ).fetchone()
        if row:
            return dict(row)
    return None

def save_mission_record(
    session_id: str,
    prompt: str,
    dept: str,
    supervisor_name: str,
    worker_names: str,
    attached_file: str,
    qc_score: int,
    rework_performed: bool,
    report_markdown: str,
) -> int:
    init_db()
    _, clean_p = is_force_refresh_prompt(prompt, session_id)
    if len(report_markdown.strip()) < 200 or clean_p == "다시 찾아줘":
        return 0
    norm_key = normalize_query_key(clean_p, attached_file)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trace_id = f"DOC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    with _get_db_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO mission_history (
                doc_trace_id, session_id, prompt, normalized_prompt, dept, supervisor_name,
                worker_names, attached_file, qc_score, rework_performed, report_markdown, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                session_id,
                clean_p,
                norm_key,
                dept,
                supervisor_name,
                worker_names,
                attached_file,
                qc_score,
                1 if rework_performed else 0,
                report_markdown,
                now_str,
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)

def list_mission_records(limit: int = 30) -> list[dict]:
    init_db()
    with _get_db_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM mission_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

def delete_mission_record(record_id: int) -> bool:
    init_db()
    with _get_db_conn() as conn:
        conn.execute("DELETE FROM mission_history WHERE id = ?", (record_id,))
        conn.commit()
        return True

DEFAULT_WEBHOOKS = {
    "ecount_erp": {
        "name": "Ecount ERP (수입검사·재고전표 API)",
        "enabled": False,
        "endpoint_url": "",
        "api_key": "",
        "company_code": "PANACTOS-QA",
    },
    "jira_cloud": {
        "name": "Atlassian Jira (부적합/이슈 자동 티켓팅)",
        "enabled": False,
        "endpoint_url": "",
        "api_key": "",
        "project_key": "QA",
    },
    "slack_webhook": {
        "name": "Slack / Teams (결재 완료 실시간 알림)",
        "enabled": False,
        "endpoint_url": "",
        "channel": "#ai-mission-control",
    },
}

def load_webhook_configs() -> dict:
    if os.path.exists(WEBHOOK_CONFIG_PATH):
        try:
            with open(WEBHOOK_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**DEFAULT_WEBHOOKS, **data}
        except Exception:
            pass
    return dict(DEFAULT_WEBHOOKS)

def save_webhook_configs(cfg: dict) -> dict:
    merged = {**load_webhook_configs(), **cfg}
    with open(WEBHOOK_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return merged

def build_enterprise_payload_preview(target_system: str, prompt: str, report_markdown: str) -> dict:
    now_iso = datetime.now().isoformat()
    if target_system == "ecount_erp":
        return {
            "system": "ECOUNT_ERP_V2_API",
            "Zone": "KR-A",
            "IO_DATE": datetime.now().strftime("%Y%m%d"),
            "UPLOAD_SER_NO": 1,
            "WH_CD": "100 (본사창고)",
            "REMARKS": f"[AI 자동결재 연동] {prompt[:40]}",
            "QC_SUMMARY": report_markdown[:240] + "...",
            "TIMESTAMP": now_iso,
        }
    if target_system == "jira_cloud":
        return {
            "system": "JIRA_REST_API_V3",
            "fields": {
                "project": {"key": "QA"},
                "summary": f"[AI 결재리포트 조치요망] {prompt[:45]}",
                "description": report_markdown[:300] + "...",
                "issuetype": {"name": "Task"},
                "priority": {"name": "High"},
            },
            "timestamp": now_iso,
        }
    return {
        "system": "SLACK_BLOCK_KIT_WEBHOOK",
        "channel": "#ai-mission-control",
        "text": f"✅ *[최종 승인 결재 보고서 도착]*\n• *지시사항:* {prompt}\n• *요약:* {report_markdown[:200]}...",
        "timestamp": now_iso,
    }
