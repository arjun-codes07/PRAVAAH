"""
PRAVAAH Risk Engine Configuration — DEMO-ONLY placeholder thresholds.

WARNING: These thresholds are PLACEHOLDER values for demonstration purposes only.
They have NOT been validated against real-world data, academic literature, or
operational standards. They MUST be reviewed and validated by the team (hydrology,
geotechnical, disaster management experts) before any field deployment.

APPLIED DEFAULT: Threshold values are NOT SPECIFIED in any source document.
"""

import os

# ---------------------------------------------------------------------------
# Model metadata
# ---------------------------------------------------------------------------
MODEL_NAME = "demo-rule-baseline"
MODEL_VERSION = os.environ.get("RISK_MODEL_VERSION", "0.2-demo")

# Prediction horizon in minutes. NOT SPECIFIED; APPLIED DEFAULT 360 (6 hours).
HORIZON_MINUTES = int(os.environ.get("RISK_HORIZON_MINUTES", "360"))

# ---------------------------------------------------------------------------
# DEMO-ONLY THRESHOLD BREAKPOINTS — needs team validation
# ---------------------------------------------------------------------------
# For each metric, define breakpoints for LOW->MODERATE->HIGH->CRITICAL.
# Format: (MODERATE_threshold, HIGH_threshold, CRITICAL_threshold)
# Below MODERATE threshold = LOW.

FLOOD_THRESHOLDS = {
    # Rainfall intensity (mm/h): sustained heavy rain increases flood risk
    "rainfall_1h_mm": {
        "MODERATE": 15.0,   # DEMO-ONLY: Light-moderate rain boundary
        "HIGH": 35.0,       # DEMO-ONLY: Heavy rain boundary
        "CRITICAL": 65.0,   # DEMO-ONLY: Extreme rain boundary
    },
    # Water level (m): river/stream gauge level
    "water_level_m": {
        "MODERATE": 2.5,    # DEMO-ONLY: Watch level
        "HIGH": 4.0,        # DEMO-ONLY: Warning level
        "CRITICAL": 6.0,    # DEMO-ONLY: Danger level
    },
    # Water level rate of change (m/h): rapid rise is dangerous
    "water_level_rate_m_per_h": {
        "MODERATE": 0.1,    # DEMO-ONLY: Noticeable rise
        "HIGH": 0.3,        # DEMO-ONLY: Rapid rise
        "CRITICAL": 0.5,    # DEMO-ONLY: Flash flood rate
    },
}

LANDSLIDE_THRESHOLDS = {
    # Soil moisture (%): saturated soil is unstable
    "soil_moisture_pct": {
        "MODERATE": 55.0,   # DEMO-ONLY: Elevated moisture
        "HIGH": 75.0,       # DEMO-ONLY: High saturation
        "CRITICAL": 90.0,   # DEMO-ONLY: Near-saturation
    },
    # Slope angle (degrees): steeper slopes are more prone
    "slope_deg": {
        "MODERATE": 20.0,   # DEMO-ONLY: Moderate slope
        "HIGH": 35.0,       # DEMO-ONLY: Steep slope
        "CRITICAL": 50.0,   # DEMO-ONLY: Very steep slope
    },
    # Rainfall also contributes to landslide risk
    "rainfall_1h_mm": {
        "MODERATE": 20.0,   # DEMO-ONLY: Moderate rainfall for landslide
        "HIGH": 40.0,       # DEMO-ONLY: Heavy rainfall for landslide
        "CRITICAL": 70.0,   # DEMO-ONLY: Extreme rainfall for landslide
    },
}

# ---------------------------------------------------------------------------
# Terrain and historical modifiers
# ---------------------------------------------------------------------------
# Susceptibility score (0..1) modifier: adds to the risk score
SUSCEPTIBILITY_WEIGHT = 0.25  # DEMO-ONLY: How much susceptibility shifts the score

# Historical event modifier: recent events of same hazard type increase risk
HISTORICAL_RECENT_YEARS = 10  # Look back N years for historical events
HISTORICAL_WEIGHT = 0.10      # DEMO-ONLY: Per-event contribution cap

# ---------------------------------------------------------------------------
# Aggregation defaults (APPLIED DEFAULT; NOT SPECIFIED in documents)
# ---------------------------------------------------------------------------
# For flood: max of rainfall, water_level, water_level_rate across sensors
# For landslide: mean of soil_moisture across sensors; slope from terrain_features
# Rationale: max captures the worst-case sensor reading for flood hazards;
# mean captures the spatial average for soil saturation.

# ---------------------------------------------------------------------------
# Risk level numeric mapping for comparison and combination
# ---------------------------------------------------------------------------
LEVEL_ORDER = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
LEVEL_FROM_SCORE = [(0, "LOW"), (1, "MODERATE"), (2, "HIGH"), (3, "CRITICAL")]

def score_to_level(score: float) -> str:
    """Convert a numeric score (0-3 scale) to a risk level string.
    
    DEMO-ONLY thresholds:
      0.0 - 0.99 = LOW
      1.0 - 1.99 = MODERATE
      2.0 - 2.99 = HIGH
      3.0+        = CRITICAL
    """
    if score >= 3.0:
        return "CRITICAL"
    elif score >= 2.0:
        return "HIGH"
    elif score >= 1.0:
        return "MODERATE"
    else:
        return "LOW"


def metric_to_score(value: float, thresholds: dict) -> float:
    """Convert a metric value to a 0-3 score using threshold breakpoints.
    
    Returns:
        0.0 if below MODERATE threshold (LOW)
        1.0-1.99 if between MODERATE and HIGH
        2.0-2.99 if between HIGH and CRITICAL
        3.0 if at or above CRITICAL
    """
    if value >= thresholds["CRITICAL"]:
        return 3.0
    elif value >= thresholds["HIGH"]:
        # Interpolate between 2.0 and 3.0
        range_size = thresholds["CRITICAL"] - thresholds["HIGH"]
        if range_size > 0:
            return 2.0 + (value - thresholds["HIGH"]) / range_size
        return 2.0
    elif value >= thresholds["MODERATE"]:
        # Interpolate between 1.0 and 2.0
        range_size = thresholds["HIGH"] - thresholds["MODERATE"]
        if range_size > 0:
            return 1.0 + (value - thresholds["MODERATE"]) / range_size
        return 1.0
    else:
        # Interpolate between 0.0 and 1.0
        if thresholds["MODERATE"] > 0:
            return max(0.0, value / thresholds["MODERATE"])
        return 0.0


# ---------------------------------------------------------------------------
# Advisory text templates per risk level (no evacuation orders — PRD non-goal)
# ---------------------------------------------------------------------------
RECOMMENDED_ACTION_TEMPLATES = {
    "LOW": "No immediate action required. Continue routine monitoring of environmental conditions.",
    "MODERATE": (
        "Elevated risk detected. Increase monitoring frequency. "
        "Review preparedness plans and ensure communication channels are active. "
        "Alert field teams to standby status."
    ),
    "HIGH": (
        "High risk conditions observed. Activate emergency response protocols. "
        "Deploy monitoring teams to affected areas. "
        "Prepare evacuation resources and notify local authorities. "
        "Issue public advisories for at-risk communities."
    ),
    "CRITICAL": (
        "Critical risk level reached. Immediate coordination with all response agencies required. "
        "Recommend issuing evacuation advisories for vulnerable areas. "
        "Deploy all available rescue resources. "
        "Establish emergency communication with district and state authorities."
    ),
}

# ---------------------------------------------------------------------------
# Explanation text templates — must change when inputs change (Phase 7 requirement)
# ---------------------------------------------------------------------------
EXPLANATION_TEMPLATES = {
    "rainfall_1h": "Rainfall intensity at {value:.1f} mm/h ({level} level). {context}",
    "water_level": "Water level at {value:.3f} m ({level} level). {context}",
    "water_level_rate": "Water level rising at {value:.3f} m/h ({level} level). {context}",
    "soil_moisture": "Soil moisture at {value:.1f}% ({level} level). {context}",
    "slope_angle": "Terrain slope at {value:.1f}° ({level} level). {context}",
    "susceptibility": "Terrain susceptibility score {value:.3f} (0-1 scale). {context}",
    "historical_events": "{count} historical {hazard_type} event(s) recorded in this zone within {years} years. {context}",
}

CONTEXT_PHRASES = {
    "LOW": "Within normal range for this region.",
    "MODERATE": "Approaching thresholds that warrant increased attention.",
    "HIGH": "Exceeds warning thresholds. Active monitoring recommended.",
    "CRITICAL": "Exceeds danger thresholds. Immediate action may be required.",
}
