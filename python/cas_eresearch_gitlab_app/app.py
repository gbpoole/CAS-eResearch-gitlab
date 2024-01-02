import ipaddress
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

app = FastAPI()

# Check if a GATE_IP has been defined in the environment and parse it if so
GATE_IP = os.getenv("GATE_IP", None)
if GATE_IP:
    GATE_IP_IN = GATE_IP
    try:
        # Make sure to ignore any starting 'https://', etc.
        GATE_IP = ipaddress.ip_address(GATE_IP_IN.split('/')[-1])
    except ValueError:
        print(f"The GATE_IP (value={GATE_IP_IN}) that has been passed from the environment is invalid.")
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

@app.post("/webhook/{webhook_type}", dependencies=[Depends(gate_ip_address)])
async def receive_payload(
    request: Request,
    event_header: str = Header(...),
) -> Dict:
    """Receive wbhook event

    You can test this hook with the following:

        curl -X 'POST' 127.0.0.1:8000/webhook/ping -H 'event-header: push' -d '{"test1": 1}'

    Parameters
    ----------
    request : Request
        Request object
    event_header : str
        Event header

    Returns
    -------
    Dict:
        Event return report
    """
    event_payload = await request.json()

    if event_header == "push":
        return {"message": f"{event_header}", "payload": f"{event_payload}"}

    else:
        return {"message": "Unable to process action"}
