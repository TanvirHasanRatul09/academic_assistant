import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.synchronization.classroom_sync import COURSE_CONCURRENCY


@pytest.mark.parametrize(("course_count", "budget_seconds"), [(10, 0.75), (25, 1.25)])
def test_controlled_course_concurrency_meets_scaled_performance_budget(
    course_count: int, budget_seconds: float
) -> None:
    """Scaled fixture: every course performs four 10 ms provider waits."""
    state_lock = threading.Lock()
    active = 0
    peak_active = 0

    def simulated_course(_course: int) -> None:
        nonlocal active, peak_active
        with state_lock:
            active += 1
            peak_active = max(peak_active, active)
        try:
            for _ in range(4):
                time.sleep(0.01)
        finally:
            with state_lock:
                active -= 1

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=COURSE_CONCURRENCY) as executor:
        list(executor.map(simulated_course, range(course_count)))
    elapsed = time.perf_counter() - started

    assert COURSE_CONCURRENCY == 5
    assert peak_active == min(COURSE_CONCURRENCY, course_count)
    assert elapsed < budget_seconds
