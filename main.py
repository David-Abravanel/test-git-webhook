import json
import os
import hmac
import hashlib
import uvicorn
import asyncio
import subprocess
from queue import Queue
from typing import Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Header, BackgroundTasks
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


async def deploy_changes():
    try:
        commands = [
            ["git", "pull", "origin", "master"],
            ["/home/ubuntu/venv/bin/pip", "install", "-r", "requirements.txt"]
        ]

        for cmd in commands:
            result = subprocess.run(
                cmd,
                cwd="/home/ubuntu/test-git-webhook",
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Command output: {result.stdout}")
            await asyncio.sleep(2)  # Small delay between commands

        await asyncio.sleep(5)  # Longer delay before service reload

        subprocess.run(
            ["sudo", "systemctl", "restart", "yolo_api"], check=True)
        logger.info("Deployment completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Deployment failed: {e.stderr}")


@app.post("/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None)
):
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

    # Manage queue
    if Q.full():
        Q.get()
    Q.put(payload)

    # Check branch
    branch = payload_data.get("ref", "")
    if branch != "refs/heads/master":
        logger.info(f"Ignored webhook for branch: {branch}")
        return {"status": f"Ignored, branch is {branch}"}

    # Queue deployment as background task
    background_tasks.add_task(deploy_changes)

    return {"status": "Deployment queued"}


@app.get("/test")
async def get_num(req: Request):
    if not Q.empty():
        return {"payload": Q.get()}
    return {"status": "No payload available"}


@app.get("/test-2")
async def get_num(req: Request):
    return {"status": "112"}
# Optional: Production server configuration
# if __name__ == "__main__":
#     uvicorn.run(
#         "main:app",
#         host="0.0.0.0",
#         port=8000,
#         workers=1,
#         reload=False
#     )
