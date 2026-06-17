def score_risk(features: dict) -> dict:
    score = 0.0
    reasons: list[str] = []

    humidity = float(features.get("humidity_percent", 50))
    wind_speed = float(features.get("wind_speed", 1))
    drought_days = float(features.get("drought_duration_days", 0))
    slope = float(features.get("slope", 0))
    fuel_moisture = float(features.get("fuel_moisture", 20))
    vulnerable = float(features.get("vulnerable", 0))

    if humidity < 30:
        score += 0.2
        reasons.append("낮은 습도")
    if wind_speed >= 5:
        score += 0.2
        reasons.append("강한 풍속")
    if drought_days >= 20:
        score += 0.15
        reasons.append("장기 가뭄")
    if slope >= 15:
        score += 0.1
        reasons.append("가파른 경사")
    if fuel_moisture < 12:
        score += 0.15
        reasons.append("낮은 연료 수분")
    if vulnerable >= 1000:
        score += 0.1
        reasons.append("취약계층 밀집")

    score = min(score, 0.99)
    if score >= 0.75:
        level = "critical"
    elif score >= 0.5:
        level = "high"
    elif score >= 0.25:
        level = "medium"
    else:
        level = "low"

    return {"risk_level": level, "risk_score": round(score, 2), "key_factors": reasons}
