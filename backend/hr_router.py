import json
import re

def extract_search_query(ceo_prompt: str) -> str:
    """질문에서 핵심 고유명사(예: 제미나이, argon, SDV 등)를 최우선으로 보존하여 검색 정확도 극대화"""
    stop_words = [
        "에 대해서", "에 대해", "대해서", "관해서", "조사해서", "비교해서", "작성해줘",
        "써줘", "정리해줘", "찾아서", "알려줘", "조사해줘", "분석해줘", "포트폴리오",
        "전략 보고서", "비교 보고서", "보고서를", "보고서", "가장 많이 요구하는", "가장 많이"
    ]
    q = ceo_prompt
    for sw in stop_words:
        q = q.replace(sw, " ")
    q = re.sub(r"[^\w\s가-힣A-Za-z0-9.\-]", " ", q)
    tokens = [t.strip() for t in q.split() if len(t.strip()) >= 2]
    return " ".join(tokens[:6]) if tokens else ceo_prompt[:25]

def assemble_team(
    ceo_prompt: str,
    manual_sup_id: str | None = None,
    manual_worker_ids: list[str] | None = None,
    employee_db_path: str = "public/data/employees.json"
):
    with open(employee_db_path, "r", encoding="utf-8") as f:
        employees = json.load(f)
    emp_map = {e["id"]: e for e in employees}

    if manual_sup_id and manual_worker_ids:
        sup_id = manual_sup_id if manual_sup_id in emp_map else "sup-mkt-01"
        w_ids = [w for w in manual_worker_ids if w in emp_map][:2]
    else:
        p = ceo_prompt.lower()
        if any(k in p for k in ["채용", "인사", "기술 스택", "포트폴리오", "이력서", "면접", "jd"]):
            dept_code = "hr"
        elif any(k in p for k in ["원가", "요금", "비용", "토큰", "가격비교", "단가", "재무", "예산"]):
            dept_code = "fin"
        elif any(k in p for k in [
            "수입검사", "coa", "성적서", "품질", "불량", "검수", "qa", "iso", "13485", "9001",
            "14971", "60601", "62304", "kgmp", "fda", "820", "iatf", "16949", "apqp", "ppap",
            "14001", "45001", "rohs", "reach", "msds", "haccp", "의료기기", "절차서", "sop",
            "매뉴얼", "ppm", "capa", "파레토", "pareto", "8d", "시정조치", "위험관리"
        ]):
            dept_code = "qa"
        elif any(k in p for k in ["재고", "erp", "bom", "엑셀", "백오피스"]):
            dept_code = "erp"
        elif any(k in p for k in ["코드", "개발", "api", "파이썬", "제미나이", "argon", "모델", "llm", "gpt", "클로드"]):
            dept_code = "dev"
        elif any(k in p for k in ["통계", "데이터", "차트", "분석", "bi"]):
            dept_code = "dat"
        elif any(k in p for k in ["해외", "글로벌", "번역", "영문", "환율"]):
            dept_code = "glb"
        else:
            dept_code = "mkt"

        sup_id = f"sup-{dept_code}-01"
        w_ids = [f"wrk-{dept_code}-01", f"wrk-{dept_code}-02"]

    search_keyword = extract_search_query(ceo_prompt)

    class WorkerTask:
        def __init__(self, agent_id: str, sub_task: str, search_keyword: str):
            self.agent_id = agent_id
            self.sub_task = sub_task
            self.search_keyword = search_keyword

    class Selection:
        def __init__(self, supervisor_id: str, workers: list[WorkerTask]):
            self.supervisor_id = supervisor_id
            self.workers = workers

    workers_list = [
        WorkerTask(
            w_ids[0],
            f"Playwright 3단계 브라우저로 '{search_keyword}' 관련 글로벌/국내 웹 문서 탐색 및 팩트 추출",
            search_keyword
        ),
        WorkerTask(
            w_ids[1] if len(w_ids) > 1 else w_ids[0],
            f"팀장 QC 반려 피드백을 반영하여 '{search_keyword}' 심층 재조사 및 최종 보고서 완성",
            search_keyword
        ),
    ]
    selection = Selection(sup_id, workers_list)

    sup = emp_map[sup_id]
    nodes = [
        {"id": "ceo", "type": "agentNode", "position": {"x": 250, "y": 20}, "data": {"name": "신영호 대표 (CEO)", "dept": "경영진", "status": "DONE"}},
        {"id": sup["id"], "type": "agentNode", "position": {"x": 250, "y": 150}, "data": {"name": sup["name"], "dept": sup["dept"], "status": "WORKING"}}
    ]
    edges = [{"id": f"e-ceo-{sup['id']}", "source": "ceo", "target": sup["id"], "animated": True}]

    start_x = 250 - ((len(workers_list) - 1) * 110)
    for idx, w in enumerate(workers_list):
        wi = emp_map[w.agent_id]
        wi["search_keyword"] = w.search_keyword
        nodes.append({"id": wi["id"], "type": "agentNode", "position": {"x": start_x + (idx * 220), "y": 300}, "data": {"name": wi["name"], "dept": wi["dept"], "status": "IDLE"}})
        edges.append({"id": f"e-{sup['id']}-{wi['id']}", "source": sup["id"], "target": wi["id"], "animated": False})

    return selection, nodes, edges, emp_map
