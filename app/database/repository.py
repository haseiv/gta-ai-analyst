from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.database.models import Analysis, Replay, TrainingExample
from app.database.session import session_scope
from app.utils.time import utc_now


class AnalysisRepository:
    def create(
        self,
        analysis_id: str,
        discord_user_id: int,
        guild_id: int | None,
        filename: str,
        status: str = "QUEUED",
    ) -> Analysis:
        with session_scope() as session:
            row = Analysis(
                id=analysis_id,
                discord_user_id=discord_user_id,
                guild_id=guild_id,
                filename=filename,
                status=status,
                progress=0.0,
                created_at=utc_now(),
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row

    def get(self, analysis_id: str) -> Analysis | None:
        with session_scope() as session:
            row = session.get(Analysis, analysis_id)
            if row is not None:
                session.expunge(row)
            return row

    def exists(self, analysis_id: str) -> bool:
        return self.get(analysis_id) is not None

    def update(self, analysis_id: str, **fields: Any) -> Analysis | None:
        with session_scope() as session:
            row = session.get(Analysis, analysis_id)
            if row is None:
                return None
            for key, value in fields.items():
                setattr(row, key, value)
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row


class ReplayRepository:
    def create(self, analysis_id: str, expires_at: datetime, status: str = "AVAILABLE") -> Replay:
        with session_scope() as session:
            row = Replay(analysis_id=analysis_id, status=status, expires_at=expires_at)
            session.add(row)
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row

    def get_by_analysis(self, analysis_id: str) -> Replay | None:
        with session_scope() as session:
            row = session.scalar(select(Replay).where(Replay.analysis_id == analysis_id))
            if row is not None:
                session.expunge(row)
            return row

    def update(self, analysis_id: str, **fields: Any) -> Replay | None:
        with session_scope() as session:
            row = session.scalar(select(Replay).where(Replay.analysis_id == analysis_id))
            if row is None:
                return None
            for key, value in fields.items():
                setattr(row, key, value)
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row

    def claim_for_send(self, analysis_id: str) -> Replay | None:
        with session_scope() as session:
            row = session.scalar(select(Replay).where(Replay.analysis_id == analysis_id))
            if row is None or row.status != "AVAILABLE":
                return None
            row.status = "SENDING"
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row

    def list_expired(self, now: datetime | None = None) -> list[Replay]:
        now = now or utc_now()
        with session_scope() as session:
            rows = list(
                session.scalars(
                    select(Replay).where(
                        Replay.status.in_(["AVAILABLE", "FAILED"]),
                        Replay.expires_at <= now,
                    )
                )
            )
            for row in rows:
                session.expunge(row)
            return rows


class TrainingRepository:
    def create(self, example: TrainingExample) -> TrainingExample:
        with session_scope() as session:
            session.add(example)
            session.flush()
            session.refresh(example)
            session.expunge(example)
            return example

    def list(self, limit: int = 20) -> list[TrainingExample]:
        with session_scope() as session:
            rows = list(
                session.scalars(
                    select(TrainingExample).order_by(TrainingExample.created_at.desc()).limit(limit)
                )
            )
            for row in rows:
                session.expunge(row)
            return rows

    def get(self, example_id: int) -> TrainingExample | None:
        with session_scope() as session:
            row = session.get(TrainingExample, example_id)
            if row is not None:
                session.expunge(row)
            return row

    def delete(self, example_id: int) -> bool:
        with session_scope() as session:
            row = session.get(TrainingExample, example_id)
            if row is None:
                return False
            session.delete(row)
            return True

    def stats(self) -> dict[str, int]:
        with session_scope() as session:
            rows = list(session.scalars(select(TrainingExample)))
            counts: dict[str, int] = {}
            for row in rows:
                counts[row.category] = counts.get(row.category, 0) + 1
            counts["total"] = len(rows)
            return counts

    def by_category(self, category: str, limit: int) -> list[TrainingExample]:
        with session_scope() as session:
            rows = list(
                session.scalars(
                    select(TrainingExample)
                    .where(TrainingExample.category == category)
                    .order_by(TrainingExample.created_at.desc())
                    .limit(limit)
                )
            )
            for row in rows:
                session.expunge(row)
            return rows
