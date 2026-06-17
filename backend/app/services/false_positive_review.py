def review_false_positive(features: dict) -> dict:
    score = 0
    notes: list[str] = []

    visibility = float(features.get("visibility", 5000))
    humidity = float(features.get("humidity_percent", 50))
    wind_speed = float(features.get("wind_speed", 1))
    surface_temperature = float(features.get("surface_temperature", 20))
    fire_intensity = str(features.get("fire_intensity", "보통"))

    if visibility < 1000:
        score += 1
        notes.append("가시성이 낮아 연무/안개 오인이 가능함")
    if humidity > 85:
        score += 1
        notes.append("습도가 높아 안개성 간섭 가능성이 큼")
    if wind_speed < 1.0:
        score += 1
        notes.append("풍속이 약해 실제 확산형 연기 신호와 다를 수 있음")
    if surface_temperature < 10:
        score += 1
        notes.append("표면 온도가 낮아 강한 열 신호 근거가 약함")
    if fire_intensity == "약함":
        score += 1
        notes.append("화재 강도 정보가 약해 보수적 해석이 필요함")

    if score >= 4:
        level = "high"
    elif score >= 2:
        level = "medium"
    else:
        level = "low"

    if not notes:
        notes.append("현재 오탐 리스크는 상대적으로 낮음")

    return {"false_positive_risk": level, "uncertainty_notes": notes}
