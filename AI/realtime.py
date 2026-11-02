import asyncio
from sqlalchemy import select
from .models import Outbox


class Hub:
    def __init__(self):
        self.clients = set()

    async def publish(self, event):
        for queue in tuple(self.clients):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                self.clients.discard(queue)
                # Force the slow consumer to reconnect and resync from persisted APIs.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait({"event_type": "resync_required"})

    def deliver(self, factory, loop):
        with factory.begin() as db:
            events = db.scalars(
                select(Outbox)
                .where(Outbox.delivered == False)
                .order_by(Outbox.created_at, Outbox.id)
                .with_for_update(skip_locked=True)
                .limit(100)
            ).all()
            for event in events:
                payload = {
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "machine_id": event.asset_id,
                    "occurred_at": event.created_at.isoformat(),
                    "payload": event.payload,
                }
                asyncio.run_coroutine_threadsafe(self.publish(payload), loop).result(
                    timeout=5
                )
                event.delivered = True
