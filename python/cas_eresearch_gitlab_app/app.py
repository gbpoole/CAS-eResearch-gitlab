import ipaddress
import logging
import json
import os
import subprocess
from enum import Enum
from typing import Dict

from dotenv import load_dotenv
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

load_dotenv()

import logging.config
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'app_file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': f"{__name__}.log",
        },
    },
    'loggers': {
        f'{__name__}': {
            'handlers': ['app_file'],
            'level': 'INFO',
            'propagate': False
        },
    }
}
logging.config.dictConfig(LOGGING_CONFIG)

logger = logging.getLogger(__name__)

app = FastAPI()

# Check if a GATE_IP has been defined in the environment and parse it if so
GATE_IP = os.getenv("GATE_IP", None)
if GATE_IP:
    GATE_IP_IN = GATE_IP
    try:
        # Make sure to ignore any starting 'https://', etc.
        GATE_IP = ipaddress.ip_address(GATE_IP_IN.split('/')[-1])
    except ValueError:
        logger.error(f"The GATE_IP (value={GATE_IP_IN}) that has been passed from the environment is invalid.")
        exit(1)


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

@app.post("/", dependencies=[Depends(gate_ip_address)])
async def receive_payload(
    request: Request,
) -> Dict:
    """Receive wbhook event

    You can test this hook with the following:

        curl -X 'POST' 127.0.0.1:8000/webhook/ping -H 'event-header: push' -d '{"test1": 1}'

    Parameters
    ----------
    request : Request
        Request object

    Returns
    -------
    Dict:
        Event return report
    """
    event_payload = await request.json()

    logger.info(f"received payload: {event_payload}")
    return {"message": "Webhook received successfully"}

