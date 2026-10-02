"""Run one scheduled synchronization pass for every connected user."""

from sqlalchemy import select

from app.db.models.entities import OAuthAccount
from app.db.session import SessionLocal
from app.services.classroom.client import ClassroomError
from app.services.synchronization.classroom_sync import ClassroomSynchronizer


def main() -> None:
    with SessionLocal() as db:
        user_ids = list(
            db.scalars(
                select(OAuthAccount.user_id)
                .where(OAuthAccount.provider == "google")
                .distinct()
            )
        )
    for user_id in user_ids:
        with SessionLocal() as db:
            try:
                ClassroomSynchronizer(db, user_id).run(cooldown_seconds=0)
            except ClassroomError:
                continue



if __name__ == "__main__":
    main()

