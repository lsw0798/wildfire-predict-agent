# Architecture

## 선택
이 프로젝트는 **MVC Model2를 현대적으로 해석한 split-stack 구조**를 사용한다.

## 매핑
- View: `frontend/`
- Controller: `backend/app/api/routes/`
- Model/Domain: `backend/app/services/`, `backend/app/schemas/`, `backend/app/models/`
- Agent workflow: `backend/app/agents/`

## 이유
전통적인 JSP/Servlet형 Model2를 그대로 쓰기보다는, 프론트와 백엔드를 분리한 뒤
백엔드 내부를 Controller-Service-Model로 명확히 나누는 편이
배포성, 테스트성, AI 기능 확장성 면에서 더 유리하다.
