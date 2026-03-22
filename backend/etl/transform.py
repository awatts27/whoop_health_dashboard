"""
Transform raw WHOOP API v2 responses into flat dicts matching the Supabase schema.

Derived fields computed here:
  sleep_efficiency        = total_sleep_duration_ms / time_in_bed_ms
  sleep_debt_ms           = sleep_need_ms - total_sleep_duration_ms
  strain_to_recovery_ratio = day_strain / recovery_score
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _iso_to_date(iso_str: str | None) -> str | None:
    """Extract YYYY-MM-DD from an ISO timestamp string."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).date().isoformat()
    except (ValueError, TypeError):
        logger.warning("Could not parse date from: %s", iso_str)
        return None


# ------------------------------------------------------------------
# sleep
# ------------------------------------------------------------------

def transform_sleep(record: dict[str, Any]) -> dict[str, Any] | None:
    """Transform a single WHOOP sleep record."""
    score = record.get("score") or {}
    stage_summary = score.get("stage_summary") or {}
    sleep_needed = score.get("sleep_needed") or {}

    # WHOOP nests the start time under `start` at the top level
    date = _iso_to_date(record.get("start"))
    if not date:
        logger.warning("Skipping sleep record with no start date: %s", record.get("id"))
        return None

    total_sleep_ms: int | None = stage_summary.get("total_in_bed_time_milli")
    # WHOOP: total_light_sleep + total_slow_wave_sleep + total_rem_sleep = total_sleep
    light_ms: int | None = stage_summary.get("total_light_sleep_time_milli")
    rem_ms: int | None = stage_summary.get("total_rem_sleep_time_milli")
    sws_ms: int | None = stage_summary.get("total_slow_wave_sleep_time_milli")

    # total_sleep = sum of sleep stages (not including awake/disturbance time)
    if light_ms is not None and rem_ms is not None and sws_ms is not None:
        total_sleep_ms_derived = light_ms + rem_ms + sws_ms
    else:
        total_sleep_ms_derived = None

    time_in_bed_ms: int | None = stage_summary.get("total_in_bed_time_milli")

    sleep_need_ms: int | None = (
        (sleep_needed.get("baseline_milli") or 0)
        + (sleep_needed.get("need_from_sleep_debt_milli") or 0)
        + (sleep_needed.get("need_from_recent_strain_milli") or 0)
        + (sleep_needed.get("need_from_recent_nap_milli") or 0)
    ) or None

    sleep_debt_ms = (
        sleep_need_ms - total_sleep_ms_derived
        if sleep_need_ms is not None and total_sleep_ms_derived is not None
        else None
    )

    return {
        "date": date,
        "total_sleep_duration_ms": total_sleep_ms_derived,
        "time_in_bed_ms": time_in_bed_ms,
        "sleep_efficiency": _safe_div(total_sleep_ms_derived, time_in_bed_ms),
        "sleep_latency_ms": stage_summary.get("sleep_latency_milli"),
        "light_sleep_ms": light_ms,
        "rem_sleep_ms": rem_ms,
        "slow_wave_sleep_ms": sws_ms,
        "num_awakenings": stage_summary.get("disturbance_count"),
        "sleep_need_ms": sleep_need_ms,
        "sleep_debt_ms": sleep_debt_ms,
        "sleep_score": score.get("sleep_performance_percentage"),
    }


# ------------------------------------------------------------------
# recovery
# ------------------------------------------------------------------

def transform_recovery(record: dict[str, Any]) -> dict[str, Any] | None:
    """Transform a single WHOOP recovery record."""
    score = record.get("score") or {}
    date = _iso_to_date(record.get("created_at") or record.get("updated_at"))
    if not date:
        logger.warning("Skipping recovery record with no date: %s", record.get("cycle_id"))
        return None

    return {
        "date": date,
        "recovery_score": score.get("recovery_score"),
        "hrv_rmssd": score.get("hrv_rmssd_milli"),
        "resting_hr": score.get("resting_heart_rate"),
        "skin_temp_celsius": score.get("skin_temp_celsius"),
        "spo2_avg": score.get("spo2_percentage"),
        "spo2_min": None,  # not available in v2 recovery score payload
        "respiratory_rate": score.get("respiratory_rate"),
    }


# ------------------------------------------------------------------
# workouts
# ------------------------------------------------------------------

def transform_workout(record: dict[str, Any]) -> dict[str, Any] | None:
    """Transform a single WHOOP workout record."""
    score = record.get("score") or {}
    date = _iso_to_date(record.get("start"))
    if not date:
        logger.warning("Skipping workout record with no start date: %s", record.get("id"))
        return None

    return {
        "date": date,
        "workout_id": str(record["id"]),
        "sport_name": record.get("sport_name"),
        "duration_ms": (
            _duration_ms(record.get("start"), record.get("end"))
        ),
        "strain_score": score.get("strain"),
        "avg_hr": score.get("average_heart_rate"),
        "max_hr": score.get("max_heart_rate"),
        "calories": score.get("kilojoule") and score["kilojoule"] * 0.239006,  # kJ → kcal
    }


def _duration_ms(start_iso: str | None, end_iso: str | None) -> int | None:
    if not start_iso or not end_iso:
        return None
    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        return int((end - start).total_seconds() * 1000)
    except (ValueError, TypeError):
        return None


# ------------------------------------------------------------------
# cycles
# ------------------------------------------------------------------

def transform_cycle(record: dict[str, Any]) -> dict[str, Any] | None:
    """Transform a single WHOOP physiological cycle record."""
    score = record.get("score") or {}
    date = _iso_to_date(record.get("start"))
    if not date:
        logger.warning("Skipping cycle record with no start date: %s", record.get("id"))
        return None

    return {
        "date": date,
        "day_strain": score.get("strain"),
        "kilojoules": score.get("kilojoule"),
        "avg_hr": score.get("average_heart_rate"),
        "max_hr": score.get("max_heart_rate"),
    }


# ------------------------------------------------------------------
# Batch helpers
# ------------------------------------------------------------------

def transform_all(raw: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """
    Transform a full day's raw fetch dict (from WhoopClient.fetch_previous_day)
    into lists of clean dicts ready for upsert.
    """
    transformers = {
        "sleep": transform_sleep,
        "recovery": transform_recovery,
        "workouts": transform_workout,
        "cycles": transform_cycle,
    }

    result: dict[str, list[dict]] = {}
    for key, records in raw.items():
        fn = transformers.get(key)
        if fn is None:
            continue
        cleaned = []
        for rec in records:
            try:
                out = fn(rec)
                if out is not None:
                    cleaned.append(out)
            except Exception as exc:  # noqa: BLE001
                logger.error("Error transforming %s record: %s — %s", key, exc, rec)
        result[key] = cleaned

    return result
