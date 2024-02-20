from pydantic import BaseModel
import datetime
from typing import Dict


class EventBase(BaseModel):
    payload: Dict


class EventCreate(EventBase):
    pass


class Event(EventBase):
    id: int
    time: datetime.date
    dev_id: int

    class Config:
        from_attributes = True
