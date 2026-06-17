# Wildfire Agent Web MVP

위치 입력 기반 산불 위험 분석, 오탐 검토, 대응 가이드를 제공하는 에이전트 AI 웹 서비스입니다.

## 아키텍처
- Frontend: Next.js + TypeScript
- Backend: FastAPI + LangGraph-friendly service structure
- Architectural style: **MVC Model2-inspired split stack**
  - View: `frontend/`
  - Controller: `backend/app/api/routes/`
  - Model/Domain: `backend/app/services/`, `backend/app/schemas/`, `backend/app/models/`

## 빠른 시작
### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000 #fastapi 서버 실행
```
#### 가상환경 이름: .venv [~/backend/.venv/bin/python]
