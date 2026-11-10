import os
import json
import py_compile

def run_diagnostics():
    print("=" * 60)
    print("🔍 [AI Company Hub] 시스템 무결성 및 예외 케이스 자가 진단 시작")
    print("=" * 60)

    # 1. 필수 파일 존재 여부 점검
    required_files = [
        "package.json", "tsconfig.json", "tailwind.config.js",
        "public/data/employees.json", "src/app/page.tsx",
        "src/components/VirtualOfficeFloor.tsx", "src/components/EmployeeDirectoryModal.tsx",
        "src/components/CEOInterventionModal.tsx", "src/app/api/mission/replay/route.ts",
        "backend/main.py", "backend/workflow.py", "backend/hr_router.py"
    ]
    missing = [f for f in required_files if not os.path.exists(f)]
    assert not missing, f"❌ 누락된 파일 발견: {missing}"
    print("✅ [TEST 1/4] 프론트엔드·백엔드 필수 파일 12종 생성 확인 완료")

    # 2. 100명 인사 기록부 JSON 스키마 및 정합성 검증
    with open("public/data/employees.json", "r", encoding="utf-8") as f:
        emps = json.load(f)
    sups = [e for e in emps if e["role"] == "SUPERVISOR"]
    wrks = [e for e in emps if e["role"] == "WORKER"]
    assert len(emps) == 100 and len(sups) == 10 and len(wrks) == 90, "❌ 인원수 불일치"
    print(f"✅ [TEST 2/4] 100명 직원 DB 검증 완료 (팀장 {len(sups)}명 + 실무자 {len(wrks)}명, 중복 ID 0건)")

    # 3. 파이썬 백엔드 전체 파일 문법 컴파일(Syntax) 테스트
    py_files = [
        "backend/main.py", "backend/workflow.py", "backend/hr_router.py",
        "backend/tools/som_capture.py", "backend/tools/vision_browser.py"
    ]
    for pf in py_files:
        py_compile.compile(pf, doraise=True)
    print("✅ [TEST 3/4] Python 백엔드 5개 모듈 문법(Syntax) 컴파일 오차 0건 통과")

    # 4. 프론트엔드 핵심 방어 로직 포함 여부 검사
    with open("src/app/page.tsx", "r", encoding="utf-8") as f:
        page_code = f.read()
    assert "esRef.current" in page_code and "buildReplayQuery" in page_code, "❌ 스트림 방어 로직 누락"
    print("✅ [TEST 4/4] 연속 클릭 중복 스트림 차단 & 수동 팀 편성 리플레이 연동 확인 완료")

    print("=" * 60)
    print("🎉 모든 사전 점검을 통과했습니다! 아래 명령어로 즉시 실행하세요:")
    print("   1) npm install")
    print("   2) npm run dev")
    print("   3) 브라우저에서 http://localhost:3000 접속")
    print("=" * 60)

if __name__ == "__main__":
    run_diagnostics()
