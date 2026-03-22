from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_session

router = APIRouter()


class JournalEntry(BaseModel):
    notes: Optional[str] = None
    alcohol: bool = False
    travel: bool = False
    sauna: bool = False
    cold_plunge: bool = False
    fasted_training: bool = False


@router.get("")
def get_journal(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_session),
):
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = db.execute(
        text("""
            SELECT date, notes, alcohol, travel, sauna, cold_plunge, fasted_training
            FROM journal
            WHERE date >= :since
            ORDER BY date DESC
        """),
        {"since": since},
    ).mappings().all()
    return [dict(r) for r in rows]


@router.post("/{entry_date}", status_code=status.HTTP_200_OK)
def upsert_journal(
    entry_date: date,
    entry: JournalEntry,
    db: Session = Depends(get_session),
):
    db.execute(
        text("""
            INSERT INTO journal (date, notes, alcohol, travel, sauna, cold_plunge, fasted_training, created_at)
            VALUES (:date, :notes, :alcohol, :travel, :sauna, :cold_plunge, :fasted_training, NOW())
            ON CONFLICT (date) DO UPDATE SET
                notes           = EXCLUDED.notes,
                alcohol         = EXCLUDED.alcohol,
                travel          = EXCLUDED.travel,
                sauna           = EXCLUDED.sauna,
                cold_plunge     = EXCLUDED.cold_plunge,
                fasted_training = EXCLUDED.fasted_training,
                created_at      = EXCLUDED.created_at
        """),
        {
            "date": entry_date.isoformat(),
            "notes": entry.notes,
            "alcohol": entry.alcohol,
            "travel": entry.travel,
            "sauna": entry.sauna,
            "cold_plunge": entry.cold_plunge,
            "fasted_training": entry.fasted_training,
        },
    )
    db.commit()
    return {"date": entry_date.isoformat(), "status": "upserted"}
