from fastapi import FastAPI
from pydantic import BaseModel

from agent.agent_loop import run_agent


app = FastAPI(
    title="Autonomous AI Employee",
    description="AI customer support task execution agent",
    version="1.0.0",
)


class TaskRequest(BaseModel):
    task: str


@app.get("/")
def home():
    return {
        "name": "Autonomous AI Employee",
        "status": "running",
    }


@app.post("/execute-task")
def execute_task(request: TaskRequest):

    result = run_agent(request.task)

    return result   