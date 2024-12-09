import json
import os
import hmac
import hashlib
import uvicorn
import subprocess
from queue import Queue
from typing import Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Header
import logging

# Initialize FastAPI app
app = FastAPI(title="YOLO Detection Service")
# Logger configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

Q = Queue(maxsize=3)

# Fetch webhook secret with error handling
WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET')
if not WEBHOOK_SECRET:
    logger.error("GitHub webhook secret is not set")
    raise ValueError("GitHub webhook secret must be configured")


@app.post("/webhook")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None)
):
    """
    Endpoint to handle GitHub webhook for deployment automation.
    """
    # Validate signature first
    if not x_hub_signature_256:
        logger.warning("Missing signature header")
        raise HTTPException(status_code=400, detail="Missing signature header")

    # Read payload
    payload = await request.body()

    # Verify GitHub signature
    secret = WEBHOOK_SECRET.encode()
    expected_signature = "sha256=" + hmac.new(
        key=secret,
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(x_hub_signature_256, expected_signature):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse JSON payload
    try:
        payload_data: Dict[str, Any] = json.loads(payload)
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON payload")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Check branch
    branch = payload_data.get("ref", "")
    if branch != "refs/heads/master":
        logger.info(f"Ignored webhook for branch: {branch}")
        return {"status": f"Ignored, branch is {branch}"}

    # check if the queue is ave..
    if Q.full():
        Q.get()

    Q.put(payload)

    # Execute deployment steps with comprehensive error handling
    try:

        commands = [
            ["git", "pull", "origin", "master"],
            ["/home/ubuntu/venv/bin/pip", "install", "-r", "requirements.txt"],
            ["sudo", "systemctl", "reload", "yolo_api"]
        ]

        for cmd in commands:
            subprocess.run(
                cmd, cwd="/home/ubuntu/test-git-webhook", check=True)

        return {"status": "Deployment successful"}

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Deployment failed: {e}")


@app.get("/test")
async def get_num(req: Request):
    if not Q.empty():
        return {"payload": Q.get()}

    return {"status": "No payload available"}


@app.get("/david-1234")
async def get_name():
    return {"name": "fffffffffffff-1"}


# Optional: Production server configuration
# if __name__ == "__main__":
#     uvicorn.run(
#         "main:app",
#         host="0.0.0.0",
#         port=8000,
#         workers=1,
#         reload=False
#     )
