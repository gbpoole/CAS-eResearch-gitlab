from sqlalchemy.orm import Session
import datetime
from typing import Dict

from . import models, schemas


def get_events(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Event).offset(skip).limit(limit).all()


def create_event(db: Session, time:datetime.date, payload: Dict):
    # Get the webhook event ID from the payload
    try:
        dev_id = payload['user']['id']
    except KeyError as e:
        raise models.CreateEventError("Missing event user ID in payload JSON") from e
    db_event = models.Event(dev_id = dev_id, time=time, payload=payload)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event
