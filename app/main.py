"""FastAPI entry point for the Autonomous Customer Support AI Employee."""
import logging
import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent.agent_loop import run_agent, list_pending_approvals, decide_approval

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Autonomous AI Employee",
    description=(
        "Prototype customer-support agent using Gemini tool calling and SQLite. "
        "Refund processing and logistics escalation are not integrated."
    ),
    version="1.1.0",
)


class TaskRequest(BaseModel):
    task: str = Field(min_length=3, max_length=4000, description="Customer-support task")


class ApprovalDecision(BaseModel):
    approved: bool
    reviewer: str = Field(default="api reviewer", min_length=1, max_length=100)


@app.get("/")
def home():
    return {"name": "Autonomous AI Employee", "status": "running", "version": app.version}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/execute-task")
def execute_task(request: TaskRequest):
    """Run one task. The Gemini request is synchronous in this prototype."""
    try:
        return run_agent(request.task.strip())
    except Exception:
        logger.exception("Unhandled error while executing agent task")
        raise HTTPException(
            status_code=500,
            detail="The task could not be completed due to an internal error.",
        )


@app.get("/approvals/pending")
def pending_approvals():
    """List approval requests awaiting a human decision."""
    return {"approvals": list_pending_approvals()}


@app.post("/approvals/{approval_id}/decision")
def approval_decision(approval_id: str, decision: ApprovalDecision):
    """Record a human decision. This does not execute a refund or other payment."""
    result = decide_approval(approval_id, decision.approved, decision.reviewer)
    if result is None:
        raise HTTPException(status_code=404, detail="Approval request not found.")
    if result.get("status") != ("approved" if decision.approved else "rejected"):
        raise HTTPException(status_code=409, detail="This approval request has already been decided.")
    return {
        "approval": result,
        "note": "Recording approval does not process a refund; no refund integration exists.",
    }
