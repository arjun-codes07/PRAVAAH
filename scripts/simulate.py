"""
PRAVAAH Simulator — Phase 4 Scenario & Telemetry Simulation Tool.

Usage:
  python -m scripts.simulate --scenario baseline|flood_escalation|landslide_escalation
                             [--speed N] [--mode simulated|replayed]
                             [--silence-node HP-MANDI-00X] [--steps N]
                             [--api-url http://127.0.0.1:8000] [--direct]

Features:
- Authenticates against PRAVAAH API (or uses in-process client if --direct or API unreachable)
- Ingests telemetry payloads via POST /api/v1/ingest/telemetry
- Supports scenario profiles:
    * baseline: normal seasonal conditions (LOW risk)
    * flood_escalation: rising rainfall and water levels (LOW -> MODERATE -> HIGH -> CRITICAL)
    * landslide_escalation: high rainfall and saturated soil moisture on steep slopes
- Simulates stale sensor behavior via --silence-node
- Observes data_origin: SIMULATED or REPLAYED
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pravaah.simulator")

DEFAULT_API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
DEFAULT_EMAIL = os.environ.get("SIMULATOR_EMAIL", "officer@demo.pravaah.local")
DEFAULT_PASSWORD = os.environ.get("SIMULATOR_PASSWORD", os.environ.get("SEED_PASSWORD_OFFICER", "DemoOfficer123!"))

ALL_NODES = [
    "HP-MANDI-001",
    "HP-MANDI-002",
    "HP-MANDI-003",
    "HP-MANDI-004",
    "HP-MANDI-005",
]


class SimulatorClient:
    """Client for posting telemetry either via live HTTP API or in-process TestClient."""

    def __init__(self, base_url: str, email: str, password: str, direct: bool = False):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.direct = direct
        self.token: Optional[str] = None
        self._test_client = None

        if self.direct:
            self._init_direct_client()
        else:
            try:
                self._authenticate_http()
            except Exception as e:
                logger.warning(f"HTTP connection to {self.base_url} failed ({e}). Falling back to in-process mode.")
                self._init_direct_client()

    def _init_direct_client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        self._test_client = TestClient(app)
        res = self._test_client.post("/api/v1/auth/login", json={"email": self.email, "password": self.password})
        if res.status_code != 200:
            raise RuntimeError(f"Direct authentication failed: {res.text}")
        self.token = res.json()["access_token"]
        logger.info("Authenticated in-process client successfully.")

    def _authenticate_http(self):
        res = httpx.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"email": self.email, "password": self.password},
            timeout=5.0,
        )
        if res.status_code != 200:
            raise RuntimeError(f"HTTP login failed with status {res.status_code}: {res.text}")
        self.token = res.json()["access_token"]
        logger.info(f"Authenticated via HTTP at {self.base_url}")

    def post_telemetry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}"}
        if self._test_client is not None:
            res = self._test_client.post("/api/v1/ingest/telemetry", json=payload, headers=headers)
            if res.status_code != 201:
                raise RuntimeError(f"Ingest failed ({res.status_code}): {res.text}")
            return res.json()
        else:
            res = httpx.post(
                f"{self.base_url}/api/v1/ingest/telemetry",
                json=payload,
                headers=headers,
                timeout=10.0,
            )
            if res.status_code != 201:
                raise RuntimeError(f"Ingest failed ({res.status_code}): {res.text}")
            return res.json()


def generate_payload(
    node_id: str,
    scenario: str,
    step: int,
    total_steps: int,
    timestamp: datetime,
    mode: str,
) -> Dict[str, Any]:
    """Generate physically plausible telemetry values for the chosen scenario step."""
    # Base baseline values
    rainfall = 2.0
    soil = 35.0
    water = 1.2
    slope = 15.0
    temp = 22.0
    humidity = 60.0

    progress = step / max(1, total_steps - 1)  # 0.0 to 1.0

    if scenario == "baseline":
        rainfall = round(1.0 + (step % 3) * 1.5, 2)
        soil = round(32.0 + (step % 4) * 2.0, 2)
        water = round(1.1 + (step % 3) * 0.15, 3)
        temp = round(21.0 + (step % 2) * 1.0, 1)
        humidity = round(55.0 + (step % 5) * 3.0, 1)

    elif scenario == "flood_escalation":
        if node_id in ("HP-MANDI-001", "HP-MANDI-005"):
            # Target focus zones: Mandi Town & Pandoh Dam
            # Escalating from normal to extreme
            rainfall = round(5.0 + progress * 75.0, 2)       # 5mm -> 80mm
            water = round(1.5 + progress * 6.5, 3)           # 1.5m -> 8.0m
            soil = round(40.0 + progress * 50.0, 2)          # 40% -> 90%
            humidity = min(99.0, round(70.0 + progress * 28.0, 1))
            temp = round(22.0 - progress * 4.0, 1)
        else:
            rainfall = round(3.0 + progress * 20.0, 2)
            water = round(1.2 + progress * 1.5, 3)
            soil = round(35.0 + progress * 25.0, 2)

    elif scenario == "landslide_escalation":
        if node_id in ("HP-MANDI-003", "HP-MANDI-004"):
            # Jogindernagar / Karsog hilly terrain
            slope = 38.0
            soil = round(50.0 + progress * 46.0, 2)          # 50% -> 96% (saturated)
            rainfall = round(10.0 + progress * 60.0, 2)      # 10mm -> 70mm
            water = round(1.3 + progress * 2.0, 3)
            humidity = min(98.0, round(75.0 + progress * 22.0, 1))
        else:
            rainfall = round(4.0 + progress * 15.0, 2)
            soil = round(40.0 + progress * 20.0, 2)

    return {
        "node_id": node_id,
        "timestamp": timestamp.isoformat(),
        "rainfall_1h": rainfall,
        "soil_moisture": min(99.99, max(0.0, soil)),
        "water_level": max(0.0, water),
        "slope_angle": slope,
        "temperature": temp,
        "humidity": min(100.0, max(0.0, humidity)),
        "data_origin": mode,
    }


def run_simulation(
    scenario: str = "flood_escalation",
    speed: float = 1.0,
    mode: str = "SIMULATED",
    silence_node: Optional[str] = None,
    steps: int = 5,
    api_url: str = DEFAULT_API_URL,
    direct: bool = False,
):
    """Execute the simulation run across nodes and steps."""
    logger.info("=" * 60)
    logger.info("PRAVAAH TELEMETRY SIMULATOR")
    logger.info(f"Scenario:     {scenario}")
    logger.info(f"Mode:         {mode}")
    logger.info(f"Steps:        {steps}")
    logger.info(f"Speed:        {speed}s per step")
    logger.info(f"Silenced:     {silence_node or 'None'}")
    logger.info("=" * 60)

    client = SimulatorClient(base_url=api_url, email=DEFAULT_EMAIL, password=DEFAULT_PASSWORD, direct=direct)

    active_nodes = [n for n in ALL_NODES if n != silence_node]
    if silence_node:
        logger.warning(f"Sensor node '{silence_node}' is SILENCED (simulating telemetry drop / stale condition)")

    now = datetime.now(timezone.utc)

    for s in range(steps):
        step_time = now + timedelta(minutes=s * 15)
        logger.info(f"\n--- Step {s + 1}/{steps} [Virtual time: {step_time.strftime('%Y-%m-%d %H:%M:%S UTC')}] ---")

        for node_id in active_nodes:
            payload = generate_payload(
                node_id=node_id,
                scenario=scenario,
                step=s,
                total_steps=steps,
                timestamp=step_time,
                mode=mode,
            )

            try:
                res = client.post_telemetry(payload)
                obs_id = res.get("observation_id")
                q_status = res.get("quality_status")
                logger.info(
                    f"[{node_id}] -> Obs #{obs_id} ({q_status}) | "
                    f"Rain: {payload['rainfall_1h']}mm, Water: {payload['water_level']}m, "
                    f"Soil: {payload['soil_moisture']}%, Temp: {payload['temperature']}C"
                )
            except Exception as e:
                logger.error(f"[{node_id}] Failed: {e}")

        if s < steps - 1 and speed > 0:
            time.sleep(speed)

    logger.info("\nSimulation run complete!")


def main():
    parser = argparse.ArgumentParser(description="PRAVAAH Telemetry Simulator")
    parser.add_argument(
        "--scenario",
        choices=["baseline", "flood_escalation", "landslide_escalation"],
        default="flood_escalation",
        help="Simulation scenario profile",
    )
    parser.add_argument("--speed", type=float, default=1.0, help="Seconds between simulation steps (default: 1.0)")
    parser.add_argument(
        "--mode",
        choices=["SIMULATED", "REPLAYED"],
        default="SIMULATED",
        help="Data origin tag (SIMULATED or REPLAYED)",
    )
    parser.add_argument(
        "--silence-node",
        type=str,
        default=None,
        help="Silence a sensor node (e.g. HP-MANDI-001) to simulate failure/staleness",
    )
    parser.add_argument("--steps", type=int, default=5, help="Number of telemetry cycles to send (default: 5)")
    parser.add_argument("--api-url", type=str, default=DEFAULT_API_URL, help="Base URL of PRAVAAH API")
    parser.add_argument("--direct", action="store_true", help="Force in-process execution without HTTP server")

    args = parser.parse_args()
    run_simulation(
        scenario=args.scenario,
        speed=args.speed,
        mode=args.mode.upper(),
        silence_node=args.silence_node,
        steps=args.steps,
        api_url=args.api_url,
        direct=args.direct,
    )


if __name__ == "__main__":
    main()
