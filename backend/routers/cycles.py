from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_session

router = APIRouter()


@router.get("")
def get_cycles(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_session),
):
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = db.execute(
        text("""
            SELECT date, day_strain, kilojoules, avg_hr, max_hr
            FROM cycles
            WHERE date >= :since
            ORDER BY date DESC
        """),
        {"since": since},
    ).mappings().all()
    return [dict(r) for r in rows]
