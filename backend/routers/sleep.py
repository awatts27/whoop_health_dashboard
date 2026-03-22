from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_session

router = APIRouter()


@router.get("")
def get_sleep(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_session),
):
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = db.execute(
        text("""
            SELECT date, total_sleep_duration_ms, time_in_bed_ms,
                   sleep_efficiency, sleep_latency_ms, light_sleep_ms,
                   rem_sleep_ms, slow_wave_sleep_ms, num_awakenings,
                   sleep_need_ms, sleep_debt_ms, sleep_score
            FROM sleep
            WHERE date >= :since
            ORDER BY date DESC
        """),
        {"since": since},
    ).mappings().all()
    return [dict(r) for r in rows]
