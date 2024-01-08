import ipaddress
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
    logger.info("Token configured")

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
        logger.error(f"Received request does not have a 'X-Gitlab-Token' entry in it's header: {request.headers}")
        raise HTTPException( status.HTTP_401_UNAUTHORIZED, "Token not specified")
    if request_token != TOKEN:
        raise HTTPException( status.HTTP_401_UNAUTHORIZED, f"Invalid token ({request_token}).")
    return

app = FastAPI()

@app.post("/", dependencies=[Depends(gate_ip_address),Depends(check_token)])
async def receive_payload( request: Request) -> Dict:
    """Receive webhook event

    You can test this hook with the following:

      $ uvicorn cas_eresearch_gitlab_app.app:app --reload
      $ curl -X 'POST' http://127.0.0.1:8000 -H 'X-Gitlab-Token: 123' -d '{"test": 1}'

    Parameters
    ----------
    request : Request
        Request object

    Returns
    -------
    Dict:
        Event status report
    """

    # Try to obtain the webhook payload
    try:
        event_payload = await request.json()
    except ValueError:
        raise HTTPException( status.HTTP_400_BAD_REQUEST, "Payload not specified.")

    # Handle valid wenhooks
    logger.info(f"received payload: {event_payload}")
    return {"message": "Webhook processed successfully."}

logger.info("========== Initialisation complete ==========")
