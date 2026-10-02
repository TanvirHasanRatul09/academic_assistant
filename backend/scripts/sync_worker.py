import argparse
import logging
import time

from app.core.logging import configure_logging
from app.services.synchronization.worker import claim_and_execute, worker_identity


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the durable Classroom sync worker")
    parser.add_argument("--once", action="store_true", help="claim at most one queued run")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    configure_logging()
    logger = logging.getLogger(__name__)
    identity = worker_identity()
    logger.info("sync_worker_started worker_id=%s", identity)
    while True:
        worked = claim_and_execute(identity)
        if args.once:
            return
        if not worked:
            time.sleep(max(0.1, args.poll_seconds))


if __name__ == "__main__":
    main()
