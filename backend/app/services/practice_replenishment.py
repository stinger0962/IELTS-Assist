"""App-local policy for enqueueing background learner practice top-ups."""
from collections.abc import Callable

from fastapi import BackgroundTasks, Request


def schedule_replenishment(
    request: Request,
    tasks: BackgroundTasks,
    replenish: Callable[[int], None],
    user_id: int,
) -> None:
    # Guarded fixture launchers opt out. The scheduler's flag is independent.
    if getattr(request.app.state, "practice_auto_replenishment_enabled", True):
        tasks.add_task(replenish, user_id)
