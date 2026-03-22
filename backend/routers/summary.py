"""
GET /summary — returns a pre-computed snapshot for the last 7 days.

Notable outlier detection:
  - Recovery dropped >15 pts from 30-day baseline on any day in the window
  - HRV dropped >10 ms from 30-day baseline on any day in the window

strain_recovery_flag: True if strain_to_recovery_ratio > 1.0 on 3+ of last 7 days.
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import mean
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_session

router = APIRouter()


def _avg(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    return round(mean(clean), 3) if clean else None


def _ms_to_hrs(ms: float | None) -> float | None:
    if ms is None:
        return None
    return round(ms / 3_600_000, 2)


@router.get("")
def get_summary(db: Session = Depends(get_session)) -> dict[str, Any]:
    today = date.today()
    seven_days_ago = (today - timedelta(days=7)).isoformat()
    thirty_days_ago = (today - timedelta(days=30)).isoformat()

    # ---- 7-day window from daily_summary ----
    rows_7d = db.execute(
        text("""
            SELECT date, recovery_score, hrv_rmssd, resting_hr,
                   total_sleep_duration_ms, slow_wave_sleep_ms,
                   sleep_debt_ms, day_strain, strain_to_recovery_ratio,
                   alcohol, travel, sauna, cold_plunge, fasted_training
            FROM daily_summary
            WHERE date >= :since
            ORDER BY date DESC
        """),
        {"since": seven_days_ago},
    ).mappings().all()

    # ---- 30-day window for baseline ----
    rows_30d = db.execute(
        text("""
            SELECT date, recovery_score, hrv_rmssd
            FROM daily_summary
            WHERE date >= :since
            ORDER BY date DESC
        """),
        {"since": thirty_days_ago},
    ).mappings().all()

    # ---- Compute 7-day stats ----
    hrv_7d = [r["hrv_rmssd"] for r in rows_7d]
    resting_hr_7d = [r["resting_hr"] for r in rows_7d]
    sleep_7d = [r["total_sleep_duration_ms"] for r in rows_7d]
    sws_7d = [r["slow_wave_sleep_ms"] for r in rows_7d]
    sleep_debt_7d = [r["sleep_debt_ms"] for r in rows_7d]
    recovery_7d = [r["recovery_score"] for r in rows_7d]
    strain_7d = [r["day_strain"] for r in rows_7d]
    ratio_7d = [r["strain_to_recovery_ratio"] for r in rows_7d]

    hrv_7d_avg = _avg(hrv_7d)

    # ---- 30-day baselines ----
    hrv_30d_all = [r["hrv_rmssd"] for r in rows_30d]
    recovery_30d_all = [r["recovery_score"] for r in rows_30d]
    hrv_30d_baseline = _avg(hrv_30d_all)
    recovery_30d_baseline = _avg(recovery_30d_all)

    hrv_vs_30d_baseline = (
        round(hrv_7d_avg - hrv_30d_baseline, 3)
        if hrv_7d_avg is not None and hrv_30d_baseline is not None
        else None
    )

    # ---- HRV trend (compare first half vs second half of 7d window) ----
    hrv_clean = [v for v in hrv_7d if v is not None]
    if len(hrv_clean) >= 4:
        mid = len(hrv_clean) // 2
        recent_half = hrv_clean[:mid]
        older_half = hrv_clean[mid:]
        delta = mean(recent_half) - mean(older_half)
        if delta > 1.5:
            hrv_trend = "positive"
        elif delta < -1.5:
            hrv_trend = "declining"
        else:
            hrv_trend = "flat"
    else:
        hrv_trend = "flat"

    # ---- strain_recovery_flag ----
    high_ratio_days = sum(
        1 for r in ratio_7d if r is not None and r > 1.0
    )
    strain_recovery_flag = high_ratio_days >= 3

    # ---- Notable outliers ----
    notable_outliers: list[str] = []
    if recovery_30d_baseline is not None:
        for r in rows_7d:
            if r["recovery_score"] is not None:
                drop = recovery_30d_baseline - float(r["recovery_score"])
                if drop > 15:
                    notable_outliers.append(
                        f"{r['date']}: recovery dropped {drop:.1f} pts below 30-day baseline"
                    )
    if hrv_30d_baseline is not None:
        for r in rows_7d:
            if r["hrv_rmssd"] is not None:
                drop = hrv_30d_baseline - float(r["hrv_rmssd"])
                if drop > 10:
                    notable_outliers.append(
                        f"{r['date']}: HRV dropped {drop:.1f} ms below 30-day baseline"
                    )

    # ---- Journal aggregates ----
    fasted_days = sum(1 for r in rows_7d if r["fasted_training"])
    sauna_days = sum(1 for r in rows_7d if r["sauna"])
    cold_plunge_days = sum(1 for r in rows_7d if r["cold_plunge"])

    sleep_debt_hrs_clean = [_ms_to_hrs(v) for v in sleep_debt_7d if v is not None]
    sleep_debt_7d_hrs = round(mean(sleep_debt_hrs_clean), 2) if sleep_debt_hrs_clean else None

    return {
        "hrv_rmssd_7d_avg": hrv_7d_avg,
        "hrv_trend_7d": hrv_trend,
        "hrv_vs_30d_baseline": hrv_vs_30d_baseline,
        "resting_hr_7d_avg": _avg(resting_hr_7d),
        "sleep_duration_7d_avg_hrs": _ms_to_hrs(_avg(sleep_7d)),
        "sws_7d_avg_hrs": _ms_to_hrs(_avg(sws_7d)),
        "sleep_debt_7d_hrs": sleep_debt_7d_hrs,
        "recovery_score_7d_avg": _avg(recovery_7d),
        "day_strain_7d_avg": _avg(strain_7d),
        "strain_to_recovery_ratio_7d": _avg(ratio_7d),
        "strain_recovery_flag": strain_recovery_flag,
        "fasted_training_days_7d": fasted_days,
        "sauna_days_7d": sauna_days,
        "cold_plunge_days_7d": cold_plunge_days,
        "notable_outliers": notable_outliers,
        "current_training_phase": os.environ.get("CURRENT_TRAINING_PHASE", ""),
        "last_bloodwork_date": os.environ.get("LAST_BLOODWORK_DATE", ""),
    }


import os  # noqa: E402 — placed after router definition intentionally
