@echo off
chcp 65001 > nul
title AI Company Hub - 통합 실행기
cd /d C:\Users\user\Desktop\ai-company-hub

echo [1/2] FastAPI 백엔드 서버를 새로운 창에서 실행합니다...
start cmd /k "chcp 65001 > nul && venv\Scripts\activate && uvicorn backend.main:app --reload --port 8000"

echo [2/2] Next.js 프론트엔드 서버를 새로운 창에서 실행합니다...
start cmd /k "chcp 65001 > nul && npm run dev"

echo ========================================================
echo 모든 서버 실행 명령이 완료되었습니다!
echo 백엔드 API 문서: http://127.0.0.1:8000/docs
echo 웹 관제 센터: http://localhost:3000
echo ========================================================
pause