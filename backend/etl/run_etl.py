"""
Main ETL entry point — fetch previous day's WHOOP data, transform, and upsert.

Usage:
    python run_etl.py

Environment variables required (see .env.example):
    WHOOP_CLIENT_ID, WHOOP_CLIENT_SECRET, WHOOP_ACCESS_TOKEN, WHOOP_REFRESH_TOKEN
    DATABASE_URL
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text

from whoop_client import WhoopClient
from transform import transform_all

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# Upsert helpers — one per table
# ---------------------------------------------------------------------------

SLEEP_UPSERT = text("""
INSERT INTO sleep (
    date, total_sleep_duration_ms, time_in_bed_ms, sleep_efficiency,
    sleep_latency_ms, light_sleep_ms, rem_sleep_ms, slow_wave_sleep_ms,
    num_awakenings, sleep_need_ms, sleep_debt_ms, sleep_score, created_at
) VALUES (
    :date, :total_sleep_duration_ms, :time_in_bed_ms, :sleep_efficiency,
    :sleep_latency_ms, :light_sleep_ms, :rem_sleep_ms, :slow_wave_sleep_ms,
    :num_awakenings, :sleep_need_ms, :sleep_debt_ms, :sleep_score, NOW()
)
ON CONFLICT (date) DO UPDATE SET
    total_sleep_duration_ms = EXCLUDED.total_sleep_duration_ms,
    time_in_bed_ms          = EXCLUDED.time_in_bed_ms,
    sleep_efficiency        = EXCLUDED.sleep_efficiency,
    sleep_latency_ms        = EXCLUDED.sleep_latency_ms,
    light_sleep_ms          = EXCLUDED.light_sleep_ms,
    rem_sleep_ms            = EXCLUDED.rem_sleep_ms,
    slow_wave_sleep_ms      = EXCLUDED.slow_wave_sleep_ms,
    num_awakenings          = EXCLUDED.num_awakenings,
    sleep_need_ms           = EXCLUDED.sleep_need_ms,
    sleep_debt_ms           = EXCLUDED.sleep_debt_ms,
    sleep_score             = EXCLUDED.sleep_score,
    created_at              = EXCLUDED.created_at
""")

RECOVERY_UPSERT = text("""
INSERT INTO recovery (
    date, recovery_score, hrv_rmssd, resting_hr,
    skin_temp_celsius, spo2_avg, spo2_min, respiratory_rate, created_at
) VALUES (
    :date, :recovery_score, :hrv_rmssd, :resting_hr,
    :skin_temp_celsius, :spo2_avg, :spo2_min, :respiratory_rate, NOW()
)
ON CONFLICT (date) DO UPDATE SET
    recovery_score    = EXCLUDED.recovery_score,
    hrv_rmssd         = EXCLUDED.hrv_rmssd,
    resting_hr        = EXCLUDED.resting_hr,
    skin_temp_celsius = EXCLUDED.skin_temp_celsius,
    spo2_avg          = EXCLUDED.spo2_avg,
    spo2_min          = EXCLUDED.spo2_min,
    respiratory_rate  = EXCLUDED.respiratory_rate,
    created_at        = EXCLUDED.created_at
""")

WORKOUT_UPSERT = text("""
INSERT INTO workouts (
    date, workout_id, sport_name, duration_ms, strain_score,
    avg_hr, max_hr, calories, created_at
) VALUES (
    :date, :workout_id, :sport_name, :duration_ms, :strain_score,
    :avg_hr, :max_hr, :calories, NOW()
)
ON CONFLICT (workout_id) DO UPDATE SET
    date         = EXCLUDED.date,
    sport_name   = EXCLUDED.sport_name,
    duration_ms  = EXCLUDED.duration_ms,
    strain_score = EXCLUDED.strain_score,
    avg_hr       = EXCLUDED.avg_hr,
    max_hr       = EXCLUDED.max_hr,
    calories     = EXCLUDED.calories,
    created_at   = EXCLUDED.created_at
""")

CYCLE_UPSERT = text("""
INSERT INTO cycles (date, day_strain, kilojoules, avg_hr, max_hr, created_at)
VALUES (:date, :day_strain, :kilojoules, :avg_hr, :max_hr, NOW())
ON CONFLICT (date) DO UPDATE SET
    day_strain = EXCLUDED.day_strain,
    kilojoules = EXCLUDED.kilojoules,
    avg_hr     = EXCLUDED.avg_hr,
    max_hr     = EXCLUDED.max_hr,
    created_at = EXCLUDED.created_at
""")

TABLE_UPSERTS = {
    "sleep": SLEEP_UPSERT,
    "recovery": RECOVERY_UPSERT,
    "workouts": WORKOUT_UPSERT,
    "cycles": CYCLE_UPSERT,
}


def run() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_engine(database_url)

    client = WhoopClient()
    raw = client.fetch_previous_day()
    clean = transform_all(raw)

    with engine.connect() as conn:
        for table, rows in clean.items():
            stmt = TABLE_UPSERTS.get(table)
            if stmt is None or not rows:
                continue
            for row in rows:
                conn.execute(stmt, row)
            logger.info("Upserted %d row(s) into %s", len(rows), table)
        conn.commit()

    logger.info("ETL complete.")


if __name__ == "__main__":
    run()
