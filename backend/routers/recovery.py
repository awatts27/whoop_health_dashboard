from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_session

router = APIRouter()


@router.get("")
def get_recovery(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_session),
):
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = db.execute(
        text("""
            SELECT date, recovery_score, hrv_rmssd, resting_hr,
                   skin_temp_celsius, spo2_avg, spo2_min, respiratory_rate
            FROM recovery
            WHERE date >= :since
            ORDER BY date DESC
        """),
        {"since": since},
    ).mappings().all()
    return [dict(r) for r in rows]
