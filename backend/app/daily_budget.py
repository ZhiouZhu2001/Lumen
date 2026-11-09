"""One durable UTC-day aggregate; no IPs, queries, automatic seeding or refunds."""

import math
from datetime import datetime, time, timedelta

from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from app.models import AIDailyUsage
from app.usage import UsageLimited, UsageUnavailable


class DailyBudget:
    def __init__(self, engine, cap):
        self.engine = engine
        self.cap = cap

    async def _clock(self, connection):
        now = await connection.scalar(
            select(func.timezone("UTC", func.clock_timestamp()))
        )
        retry = max(
            1,
            math.ceil(
                (
                    datetime.combine(now.date() + timedelta(days=1), time()) - now
                ).total_seconds()
            ),
        )
        return now.date(), retry

    async def snapshot(self):
        try:
            async with self.engine.connect() as connection:
                day, retry = await self._clock(connection)
                row = (
                    (
                        await connection.execute(
                            select(AIDailyUsage.__table__).where(AIDailyUsage.id == 1)
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            if row is None or row["utc_day"] > day:
                raise UsageUnavailable("Daily budget requires verified initialization")
            used = row["attempts"] if row["utc_day"] == day else 0
            return {
                "utc_day": day.isoformat(),
                "used": used,
                "daily_cap": self.cap,
                "retry_after": retry,
            }
        except SQLAlchemyError as error:
            raise UsageUnavailable("Daily budget storage is unavailable") from error

    async def check_daily(self):
        status = await self.snapshot()
        if status["used"] >= self.cap:
            raise UsageLimited(status["retry_after"], daily=True)

    async def consume_ai(self):
        try:
            async with self.engine.begin() as connection:
                day, retry = await self._clock(connection)
                result = await connection.scalar(
                    update(AIDailyUsage)
                    .where(
                        AIDailyUsage.id == 1,
                        AIDailyUsage.utc_day <= day,
                        (AIDailyUsage.utc_day < day)
                        | (AIDailyUsage.attempts < self.cap),
                    )
                    .values(
                        utc_day=day,
                        attempts=case(
                            (AIDailyUsage.utc_day < day, 1),
                            else_=AIDailyUsage.attempts + 1,
                        ),
                    )
                    .returning(AIDailyUsage.attempts)
                )
                if result is None:
                    stored_day = await connection.scalar(
                        select(AIDailyUsage.utc_day).where(AIDailyUsage.id == 1)
                    )
                    if stored_day is None or stored_day > day:
                        raise UsageUnavailable(
                            "Daily budget requires verified initialization"
                        )
                    raise UsageLimited(retry, daily=True)
            # Commit succeeds before the caller can send the HTTP attempt. A
            # crash after reservation may overcount, never grant extra attempts.
        except SQLAlchemyError as error:
            raise UsageUnavailable("Daily budget storage is unavailable") from error

    async def raise_floor(self, used, *, expected_day):
        """Explicit paused-service administration; never lower the same day's use."""
        if type(used) is not int or used < 0:
            raise ValueError("A nonnegative verified usage floor is required")
        try:
            async with self.engine.begin() as connection:
                day, _ = await self._clock(connection)
                if day != expected_day:
                    raise ValueError(
                        "UTC day changed; verify usage again before initialization"
                    )
                statement = insert(AIDailyUsage).values(
                    id=1, utc_day=day, attempts=used
                )
                result = await connection.scalar(
                    statement.on_conflict_do_update(
                        index_elements=[AIDailyUsage.id],
                        set_={
                            "utc_day": day,
                            "attempts": case(
                                (AIDailyUsage.utc_day < day, used),
                                else_=func.greatest(AIDailyUsage.attempts, used),
                            ),
                        },
                        where=AIDailyUsage.utc_day <= day,
                    ).returning(AIDailyUsage.attempts)
                )
                if result is None:
                    raise UsageUnavailable("Budget date is ahead of the database clock")
                return result
        except SQLAlchemyError as error:
            raise UsageUnavailable("Daily budget initialization failed") from error
