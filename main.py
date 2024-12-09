import json
import os
import hmac
import hashlib
import uvicorn
import subprocess
from fastapi import FastAPI, HTTPException, Request
import logging

# Initialize FastAPI app
app = FastAPI(title="YOLO Detection Service")

# Logger configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        subprocess.run(["git", "pull", "origin", "master"], check=True)

        # Activate virtual environment
        venv_activate_cmd = "./venv/bin/activate" if os.name != "nt" else ".\\venv\\Scripts\\activate"
        logger.info("Activating virtual environment...")
        subprocess.run(venv_activate_cmd, shell=True, check=True)

        # Install dependencies
        logger.info("Installing dependencies...")
        subprocess.run(
            ["pip", "install", "-r", "requirements.txt"], shell=True, check=True)

        # Restart application
        logger.info("Restarting YOLO API service...")
        subprocess.run(
            ["sudo", "systemctl", "restart", "yolo_api"], check=True)

        logger.info("Deployment completed successfully.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Deployment failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Deployment failed: {str(e)}"
        )

    return {"status": "Deployment successful"}


if __name__ == "__main__":
    """
    Run the FastAPI application with Uvicorn server for production.
    """
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # Listen on all network interfaces
        port=8000,
        workers=1,  # Adjust the number of workers as needed
        reload=True  # Disable reload in production
    )
