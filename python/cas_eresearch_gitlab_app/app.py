import ipaddress
import datetime
import logging
import json
import os
import subprocess
from decouple import config
from enum import Enum
from typing import Dict
from fastapi import (
    BackgroundTasks,
    Depends, 
    FastAPI,
    Header,
    HTTPException,
    Request,
    status,
)
from httpx import AsyncClient

from sqlalchemy.orm import Session

from . import crud, events, models, schemas
from .database import SessionLocal, engine

package_name = __name__.split('.')[0]

# Configure logger
logger = logging.getLogger(f'{package_name}')
handler = logging.FileHandler(f'{package_name}.log')
formatter = logging.Formatter(fmt='%(asctime)s | %(levelname)-7s | %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

logger.info("========== Initialising service ==========")

# Parse runtime configuration
GATE_IP = config('GATE_IP', default = None)
TOKEN = config('SECRET_TOKEN', default = None)
if not TOKEN:
    logger.error("No token specified by environment.")
    exit(1)
else:
    logger.info("Token configured.")

LOG_LEVEL = config('LOG_LEVEL', default = logging.DEBUG )
logger.setLevel(LOG_LEVEL)
logger.info(f"Application logging level set to {logging.getLevelName(logger.getEffectiveLevel())}.")

# Check if a GATE_IP has been defined in the environment and parse it if so
if GATE_IP:
    GATE_IP_IN = GATE_IP
    try:
        # Make sure to ignore any starting 'https://', etc.
        GATE_IP = ipaddress.ip_address(GATE_IP_IN.split('/')[-1])
    except ValueError:
        logger.error(f"The GATE_IP (value={GATE_IP_IN}) that has been passed from the environment is invalid.")
        exit(1)
    logger.info(f"IP gateing configured for {GATE_IP}.")
else:
    logger.warning("No IP gateing configured.")

async def gate_ip_address(request: Request):
    # Allow GitHub IPs only
    if GATE_IP:
        try:
            src_ip = ipaddress.ip_address(request.client.host)
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Could not hook incoming IP address"
            )
        if src_ip == GATE_IP:
            return
        else:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Not a valid incoming IP address"
            )

async def check_token(request: Request):
    try:
        request_token = request.headers['X-Gitlab-Token']
    except KeyError:
        logger.error(f"Received request does not have a 'X-Gitlab-Token' entry in it's header.")
        raise HTTPException( status.HTTP_401_UNAUTHORIZED, "Token not specified")
    if request_token != TOKEN:
        raise HTTPException( status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

models.Base.metadata.create_all(bind=engine)

@app.post("/", dependencies=[Depends(gate_ip_address),Depends(check_token)])
async def create_event( request: Request, db=Depends(get_db)) -> Dict:
    """Receive webhook event

    You can test this hook with the following:

      $ uvicorn cas_eresearch_gitlab_app.app:app --reload
      $ ./scripts/test_post.sh

    Parameters
    ----------
    request : Request
        Request object

    Returns
    -------
    Dict:
        Event status report
    """

    # Obtain the webhook payload
    try:
        event_payload = await request.json()
    except ValueError:
        raise HTTPException( status.HTTP_400_BAD_REQUEST, "Payload not specified.")

    # Set the webhook date & time
    time = datetime.datetime.now()

    # Create event and write it to the database
    try:
        event = crud.create_event(db=db,time=time,payload=event_payload)
    except models.CreateEventError as e:
        logger.error(f"Invalid payload: {e}")
        raise HTTPException( status.HTTP_400_BAD_REQUEST, "Payload invalid.")

    # Report success
    logger.info(f"Event (id={event.id}) processed successfully.")
    return {"message": "Webhook processed successfully"}


@app.get("/events", dependencies=[Depends(check_token)])
async def get_events( request: Request, db=Depends(get_db)) -> str:
    """Get webhook events

    You can test this hook with the following:

      $ uvicorn cas_eresearch_gitlab_app.app:app --reload
      $ ./scripts/test_get.sh

    Parameters
    ----------
    request : Request
        Request object

    Returns
    -------
    str:
        String containing a list of filtered events
    """

    # Read events
    ds = events.DataSet('./')

    # Report success
    logger.info(f"{ds.count()} events returned.")

    return ds.to_json()

logger.info("========== Initialisation complete ==========")
