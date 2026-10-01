"""`rigdeck service`: one background process that runs every module's task."""
from __future__ import annotations

import heapq
import logging
import signal
import time

from . import config
from .modules import MODULES

log = logging.getLogger("rigdeck")


def run():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    tasks = [(m.id, t) for m in MODULES if (t := m.service_task()) is not None]
    state = {"reload": True, "running": True}
    signal.signal(signal.SIGHUP, lambda *_: state.update(reload=True))
    signal.signal(signal.SIGTERM, lambda *_: state.update(running=False))
    signal.signal(signal.SIGINT, lambda *_: state.update(running=False))
    log.info("service started with modules: %s", ", ".join(i for i, _ in tasks) or "none")

    queue = [(0.0, i, t) for i, (_, t) in enumerate(tasks)]
    heapq.heapify(queue)
    while state["running"]:
        if state["reload"]:
            state["reload"] = False
            cfg = config.load()
            for mid, t in tasks:
                try:
                    t.reload(cfg)
                except Exception:
                    log.exception("%s: reload failed", mid)
        if not queue:
            time.sleep(1)
            continue
        due, i, task = queue[0]
        now = time.monotonic()
        if due > now:
            time.sleep(min(due - now, 0.5))  # wake regularly to notice signals
            continue
        heapq.heappop(queue)
        try:
            delay = task.tick(now)
        except Exception:
            log.exception("%s: task failed", tasks[i][0])
            delay = 5.0
        heapq.heappush(queue, (now + delay, i, task))
    for _, t in tasks:
        t.close()
    log.info("service stopped")
