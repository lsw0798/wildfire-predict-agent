# Local runtime/env checklist

## Frontend (`frontend/.env.local`)

Required:
- `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`
- `NEXT_PUBLIC_KAKAO_JAVASCRIPT_KEY=<Kakao JavaScript key>`

Kakao Maps SDK requirements:
1. The Kakao Developers app that owns the JavaScript key must have `OPEN_MAP_AND_LOCAL` enabled.
2. Web platform domains should include both:
   - `http://localhost:3000`
   - `http://127.0.0.1:3000`

If either is missing, the UI falls back and shows a diagnostic message instead of the map.

## Backend (`backend/.env`)

Required:
- `APP_NAME`
- `APP_VERSION`
- `WILDFIRE_API_BASE_URL`
- `WILDFIRE_API_KEY`
- `WILDFIRE_DATA_DIR=data`
- `WILDFIRE_PROCESSED_DATA_PATH=data/processed/incidents.json`
- `BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000`

Optional:
- `KAKAO_REST_API_KEY`
  - useful for future server-side geocoding / local search integration
  - do **not** expose this key as a `NEXT_PUBLIC_*` variable

## Safe templates

Copy from:
- `frontend/.env.example`
- `backend/.env.example`
