from sqlalchemy import Column, Integer, DateTime, JSON

from .database import Base


class CreateEventError(Exception):
    """Raised when a failure is encountered while creating an event"""

    pass


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    time = Column(DateTime, index=True)
    dev_id = Column(Integer, index=True)
    payload = Column(JSON)
