import asyncio
from datetime import datetime
import zoneinfo

KST = zoneinfo.ZoneInfo("Asia/Seoul")


async def wait_until(scheduled_at: datetime) -> None:
    """scheduled_at까지 대기 (Controller 스케줄 자체가 랜덤이므로 추가 jitter 없음)"""
    now = datetime.now(tz=KST)
    delay = (scheduled_at - now).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)


async def sleep_until_next_0630_kst() -> None:
    """다음날 06:30 KST까지 sleep"""
    from datetime import date, timedelta
    now = datetime.now(tz=KST)
    target = datetime(now.year, now.month, now.day, 6, 30, tzinfo=KST)
    if now >= target:
        target += timedelta(days=1)
    delay = (target - now).total_seconds()
    await asyncio.sleep(delay)
