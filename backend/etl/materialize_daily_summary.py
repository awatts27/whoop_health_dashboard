"""
Materialize daily_summary for a given date by joining sleep, recovery,
cycles, workouts, and journal, then upsert into daily_summary.

Usage:
    python materialize_daily_summary.py [YYYY-MM-DD]

If no date is supplied, defaults to yesterday (UTC).

Environment variables required:
    DATABASE_URL — PostgreSQL connection string (Supabase)
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

UPSERT_SQL = text("""
INSERT INTO daily_summary (
    date,
    recovery_score, hrv_rmssd, resting_hr,
    skin_temp_celsius, spo2_avg, respiratory_rate,
    total_sleep_duration_ms, slow_wave_sleep_ms,
    sleep_efficiency, sleep_latency_ms, sleep_debt_ms,
    day_strain, total_calories,
    strain_to_recovery_ratio,
    alcohol, travel, sauna, cold_plunge, fasted_training,
    created_at
)
VALUES (
    :date,
    :recovery_score, :hrv_rmssd, :resting_hr,
    :skin_temp_celsius, :spo2_avg, :respiratory_rate,
    :total_sleep_duration_ms, :slow_wave_sleep_ms,
    :sleep_efficiency, :sleep_latency_ms, :sleep_debt_ms,
    :day_strain, :total_calories,
    :strain_to_recovery_ratio,
    :alcohol, :travel, :sauna, :cold_plunge, :fasted_training,
    NOW()
)
ON CONFLICT (date) DO UPDATE SET
    recovery_score              = EXCLUDED.recovery_score,
    hrv_rmssd                   = EXCLUDED.hrv_rmssd,
    resting_hr                  = EXCLUDED.resting_hr,
    skin_temp_celsius           = EXCLUDED.skin_temp_celsius,
    spo2_avg                    = EXCLUDED.spo2_avg,
    respiratory_rate            = EXCLUDED.respiratory_rate,
    total_sleep_duration_ms     = EXCLUDED.total_sleep_duration_ms,
    slow_wave_sleep_ms          = EXCLUDED.slow_wave_sleep_ms,
    sleep_efficiency            = EXCLUDED.sleep_efficiency,
    sleep_latency_ms            = EXCLUDED.sleep_latency_ms,
    sleep_debt_ms               = EXCLUDED.sleep_debt_ms,
    day_strain                  = EXCLUDED.day_strain,
    total_calories              = EXCLUDED.total_calories,
    strain_to_recovery_ratio    = EXCLUDED.strain_to_recovery_ratio,
    alcohol                     = EXCLUDED.alcohol,
    travel                      = EXCLUDED.travel,
    sauna                       = EXCLUDED.sauna,
    cold_plunge                 = EXCLUDED.cold_plunge,
    fasted_training             = EXCLUDED.fasted_training,
    created_at                  = EXCLUDED.created_at
""")


def materialize(target_date: date) -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_engine(database_url)

    date_str = target_date.isoformat()
    logger.info("Materializing daily_summary for %s", date_str)

    with engine.connect() as conn:
        # ----- recovery -----
        rec = conn.execute(
            text("""
                SELECT recovery_score, hrv_rmssd, resting_hr,
                       skin_temp_celsius, spo2_avg, respiratory_rate
                FROM recovery WHERE date = :d
            """),
            {"d": date_str},
        ).mappings().fetchone() or {}

        # ----- sleep -----
        slp = conn.execute(
            text("""
                SELECT total_sleep_duration_ms, slow_wave_sleep_ms,
                       sleep_efficiency, sleep_latency_ms, sleep_debt_ms
                FROM sleep WHERE date = :d
            """),
            {"d": date_str},
        ).mappings().fetchone() or {}

        # ----- cycles -----
        cyc = conn.execute(
            text("SELECT day_strain, kilojoules FROM cycles WHERE date = :d"),
            {"d": date_str},
        ).mappings().fetchone() or {}

        # ----- workouts: sum calories across all sessions -----
        wkt = conn.execute(
            text("SELECT COALESCE(SUM(calories), 0) AS total_calories FROM workouts WHERE date = :d"),
            {"d": date_str},
        ).mappings().fetchone() or {}

        # ----- journal -----
        jnl = conn.execute(
            text("""
                SELECT alcohol, travel, sauna, cold_plunge, fasted_training
                FROM journal WHERE date = :d
            """),
            {"d": date_str},
        ).mappings().fetchone() or {}

    # Derived: strain_to_recovery_ratio
    day_strain = cyc.get("day_strain")
    recovery_score = rec.get("recovery_score")
    if day_strain is not None and recovery_score and recovery_score != 0:
        strain_to_recovery_ratio = float(day_strain) / float(recovery_score)
    else:
        strain_to_recovery_ratio = None

    # Convert kilojoules from cycles to kcal for total_calories if workouts sum is 0
    total_calories = wkt.get("total_calories") or (
        float(cyc["kilojoules"]) * 0.239006 if cyc.get("kilojoules") else None
    )

    row = {
        "date": date_str,
        "recovery_score": rec.get("recovery_score"),
        "hrv_rmssd": rec.get("hrv_rmssd"),
        "resting_hr": rec.get("resting_hr"),
        "skin_temp_celsius": rec.get("skin_temp_celsius"),
        "spo2_avg": rec.get("spo2_avg"),
        "respiratory_rate": rec.get("respiratory_rate"),
        "total_sleep_duration_ms": slp.get("total_sleep_duration_ms"),
        "slow_wave_sleep_ms": slp.get("slow_wave_sleep_ms"),
        "sleep_efficiency": slp.get("sleep_efficiency"),
        "sleep_latency_ms": slp.get("sleep_latency_ms"),
        "sleep_debt_ms": slp.get("sleep_debt_ms"),
        "day_strain": day_strain,
        "total_calories": total_calories,
        "strain_to_recovery_ratio": strain_to_recovery_ratio,
        "alcohol": jnl.get("alcohol", False),
        "travel": jnl.get("travel", False),
        "sauna": jnl.get("sauna", False),
        "cold_plunge": jnl.get("cold_plunge", False),
        "fasted_training": jnl.get("fasted_training", False),
    }

    with engine.connect() as conn:
        conn.execute(UPSERT_SQL, row)
        conn.commit()

    logger.info("daily_summary upserted for %s", date_str)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = date.fromisoformat(sys.argv[1])
    else:
        target = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    materialize(target)
