import json
import os
import hmac
import hashlib
import time
import subprocess
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
import logging

# Initialize FastAPI app
app = FastAPI(title="YOLO Detection Service")

# Logger configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


def stop_service_if_active(service_name):
    """
    Stop the service if it is active, and wait until it is fully stopped.
    """
    status = subprocess.run(
        ["sudo", "systemctl", "is-active", service_name], capture_output=True, text=True
    )

    if status.stdout.strip() == "active":
        logger.info(f"Stopping {service_name} service...")
        subprocess.run(["sudo", "systemctl", "stop", service_name], check=True)

        # Wait for the service to stop
        while True:
            status = subprocess.run(
                ["sudo", "systemctl", "is-active", service_name], capture_output=True, text=True
            )
            if status.stdout.strip() == "inactive":
                logger.info(f"{service_name} service stopped successfully.")
                break
            time.sleep(1)  # Wait 1 second before checking again


def restart_service(service_name):
    """
    Restart the service after stopping it.
    """
    logger.info(f"Restarting {service_name} service...")
    subprocess.run(["sudo", "systemctl", "restart", service_name], check=True)
    logger.info(f"{service_name} service restarted successfully.")


@app.post("/webhook")
async def github_webhook(request: Request):
    """
    Endpoint to handle GitHub webhook for deployment automation.
    """
    logger.info("Webhook triggered.")

    # Read payload
    payload = await request.body()

    logger.info("Signature validated. Parsing payload...")

    # Parse JSON payload
    try:
        payload_data = json.loads(payload)
    except json.JSONDecodeError as e:
        logger.error("Failed to decode JSON payload.")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Check branch
    branch = payload_data.get("ref")
    print(branch)
    if branch != "refs/heads/master":
        logger.info(f"Ignored webhook for branch: {branch}")
        return {"status": f"Ignored, branch is {branch}"}

    logger.info("Branch validated as 'main'. Starting deployment steps.")

    # Extract GitHub signature
    github_signature = request.headers.get("X-Hub-Signature-256")
    if not github_signature:
        logger.warning("Missing signature header.")
        raise HTTPException(status_code=400, detail="Missing signature header")

    webhook_secret = os.getenv('GITHUB_WEBHOOK_SECRET')  # From GitHub settings
    if not webhook_secret:
        logger.error("Webhook secret not set in environment.")
        raise HTTPException(
            status_code=500, detail="Server misconfiguration: missing secret")

    # Validate signature
    secret = webhook_secret.encode()
    expected_signature = "sha256=" + hmac.new(
        key=secret, msg=payload, digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(github_signature, expected_signature):
        logger.warning("Invalid signature.")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Execute deployment steps
    try:
        # Pull latest changes
        logger.info("Pulling latest changes from repository...")
        subprocess.run(
            ["git", "pull", "origin", "master"],
            check=True,
            cwd="/home/ubuntu/test-git-webhook",
            capture_output=True,
            text=True
        )

        # Activate virtual environment
        logger.info("Activating virtual environment...")
        subprocess.run("../venv/bin/activate",
                       shell=True, check=True)

        # Install dependencies
        logger.info("Installing dependencies...")
        subprocess.run(
            ["pip", "install", "-r", "requirements.txt"], shell=True, check=True)

        # Stop and restart the application
        stop_service_if_active("yolo_api.service")
        restart_service("yolo_api.service")

        logger.info("Deployment completed successfully.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Deployment failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Deployment failed: {str(e)}"
        )

    return {"status": "Deployment successful"}


@app.post("/test")
async def github_webhook(request: Request):
    return 1

# if __name__ == "__main__":
#     """
#     Run the FastAPI application with Uvicorn server for production.
#     """
#     uvicorn.run(
#         "main:app",
#         host="0.0.0.0",  # Listen on all network interfaces
#         port=8000,
#         workers=1,  # Adjust the number of workers as needed
#         reload=True  # Disable reload in production
#     )
