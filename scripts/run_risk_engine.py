"""
CLI entry point: python -m scripts.run_risk_engine [--zone-id N]

Runs the PRAVAAH demo risk engine for all zones or a specific zone.
"""

import argparse
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

from app.db import SessionLocal
from app.services.risk_engine import compute_zone_risk, run_all_zones


def main():
    parser = argparse.ArgumentParser(description="PRAVAAH Risk Engine CLI (demo-rule-baseline)")
    parser.add_argument("--zone-id", type=int, default=None, help="Run for a specific zone ID only")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.zone_id:
            print(f"Running risk engine for zone {args.zone_id}...")
            pred_id = compute_zone_risk(db, args.zone_id)
            if pred_id:
                print(f"  [OK] Zone {args.zone_id}: new prediction #{pred_id}")
            else:
                print(f"  [SKIP] Zone {args.zone_id}: skipped (no non-stale VALID observations)")
        else:
            print("Running risk engine for ALL active zones...")
            results = run_all_zones(db)
            print(f"\nResults: {results['computed']} computed, {results['skipped']} skipped, {results['errors']} errors")
            for d in results["details"]:
                if d.get("skipped"):
                    print(f"  [SKIP] Zone {d['zone_id']} ({d['zone_name']}): skipped")
                elif d.get("error"):
                    print(f"  [FAIL] Zone {d['zone_id']} ({d['zone_name']}): {d['error']}")
                else:
                    print(f"  [OK] Zone {d['zone_id']} ({d['zone_name']}): prediction #{d['prediction_id']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
