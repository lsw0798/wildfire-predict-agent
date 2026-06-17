# API Contract

## POST /api/analyze
Request
```json
{
  "lat": 37.110673,
  "lon": 127.297152,
  "user_type": "공무원"
}
```

Response
```json
{
  "risk_level": "high",
  "risk_score": 0.55,
  "false_positive_risk": "medium",
  "confidence": 0.74,
  "key_factors": ["낮은 습도", "장기 가뭄"],
  "recommended_actions": ["취약계층 우선 대피 동선 점검"],
  "uncertainty_notes": ["가시성이 낮아 연무/안개 오인이 가능함"]
}
```
