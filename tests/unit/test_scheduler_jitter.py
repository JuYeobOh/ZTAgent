import pytest
from unittest.mock import patch, AsyncMock
from employee_agent.scheduler import wait_until
from datetime import datetime, timedelta
import zoneinfo

KST = zoneinfo.ZoneInfo("Asia/Seoul")


@pytest.mark.asyncio
async def test_wait_until_past_does_not_sleep() -> None:
    """과거 시각이면 sleep 호출 없음."""
    past_time = datetime(2020, 1, 1, tzinfo=KST)
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await wait_until(past_time)
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_wait_until_future_sleeps_correct_duration() -> None:
    """미래 시각이면 남은 초만큼 sleep."""
    with patch("employee_agent.scheduler.datetime") as mock_dt:
        fake_now = datetime(2026, 1, 1, 9, 0, 0, tzinfo=KST)
        mock_dt.now.return_value = fake_now

        future_time = datetime(2026, 1, 1, 9, 0, 30, tzinfo=KST)  # 30초 후
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await wait_until(future_time)

    mock_sleep.assert_awaited_once()
    slept = mock_sleep.call_args[0][0]
    assert abs(slept - 30.0) < 0.1
