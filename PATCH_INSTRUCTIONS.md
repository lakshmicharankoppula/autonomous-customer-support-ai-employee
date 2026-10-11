# Patch for Autonomous Customer Support AI Employee

This patch updates the agent's task-success calculation and adds regression tests. It is intended to be applied to the existing repository; it does not include or replace the user's local SQLite database or their `.env` secret.

## Files to replace
Copy these files into the matching paths in your existing project, overwriting the old versions:

- `agent/agent_loop.py`
- `app/main.py`
- `tests/test_agent_guardrails.py`
- `requirements.txt`

Copy `.env.example` only if you need a safe placeholder template. Do not replace your real local `.env` file.

## Run checks in Git Bash from the project root

```bash
source venv/Scripts/activate
python -m pip install -r requirements.txt
python -m py_compile agent/agent_loop.py app/main.py
python -m unittest discover -s tests -v
```

## Start the API

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080/docs`.

## Important behavior

- A successfully created approval request can count as successful execution of the approval-request task.
- `success` does not mean the underlying business issue is resolved.
- Asking the agent to actually process a refund remains unsuccessful because there is no refund-processing integration.
- The human approval endpoint only records a decision. It does not execute a payment or refund.
- Approval records remain in process memory and are lost if the API process restarts; use a persistent store before production deployment.
