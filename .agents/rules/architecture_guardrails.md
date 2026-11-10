# AI Company Hub - Antigravity Agent Rules
1. 아키텍처 보존: 백엔드 수정 시 반드시 `venv\Scripts\python tests/test_enterprise_suite.py`를 실행하여 5대 엔지니어링 기둥 테스트가 통과하는지 검증하세요.
2. 비동기 원칙: 모든 외부 네트워크 통신은 `httpx.AsyncClient`를 유지하고 동기 블로킹 I/O를 사용하지 마세요.
3. 세션 격리: 파일 업로드(`SESSION_UPLOADS`) 및 엑셀 테이블(`SESSION_TABLES`)은 반드시 `session_id`를 통해 격리하세요.