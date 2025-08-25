from fastapi import FastAPI, HTTPException, Request, Header
import os
import uuid
import httpx

app = FastAPI(title="PM CoachBot")

# In-memory store for dry-run plans (replace with DB in prod)
RUNS = {}

# Env vars
API_KEY = os.getenv("API_KEY", "admin-123")
SUBSCRIPTION_KEY = os.getenv("SUBSCRIPTION_KEY", "sub-abc")

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_DEFAULT_CHANNEL_ID = os.getenv("SLACK_DEFAULT_CHANNEL_ID")

@app.get("/healthz")
async def healthz():
    return {"ok": True, "service": "pm-coachbot", "status": "healthy"}

@app.post("/runs/plan")
async def create_plan(
    request: Request,
    x_subscription_key: str = Header(None)
):
    if x_subscription_key != SUBSCRIPTION_KEY:
        raise HTTPException(status_code=403, detail="Invalid subscription key")

    body = await request.json()
    run_id = str(uuid.uuid4())
    RUNS[run_id] = {
        "status": "pending",
        "intent": body.get("intent"),
        "params": body.get("params"),
        "dry_run": True
    }
    return {"run_id": run_id, "dry_run": True, "details": RUNS[run_id]}

@app.post("/runs/{run_id}/approve")
async def approve_run(run_id: str, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    if run_id not in RUNS:
        raise HTTPException(status_code=404, detail="Run ID not found")

    run = RUNS[run_id]
    run["dry_run"] = False
    run["status"] = "executed"

    # Execute Jira tasks
    if run.get("params", {}).get("jira"):
        await create_jira_issues(run["params"]["jira"], dry_run=False)

    # Execute Slack tasks
    if run.get("params", {}).get("slack"):
        await post_slack_message(run["params"]["slack"], dry_run=False)

    return {"run_id": run_id, "status": "executed"}

@app.post("/jira/create-issues")
async def create_jira_issues(params: dict, dry_run: bool = True):
    if dry_run or not (JIRA_BASE_URL and JIRA_EMAIL and JIRA_API_TOKEN):
        return {"dry_run": True, "params": params}

    async with httpx.AsyncClient() as client:
        # Simplified Jira issue creation example
        resp = await client.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue",
            auth=(JIRA_EMAIL, JIRA_API_TOKEN),
            json=params
        )
    return resp.json()

@app.post("/slack/post")
async def post_slack_message(params: dict, dry_run: bool = True):
    if dry_run or not SLACK_BOT_TOKEN:
        return {"dry_run": True, "params": params}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            json={"channel": params.get("channel", SLACK_DEFAULT_CHANNEL_ID),
                  "text": params.get("message")}
        )
    return resp.json()
