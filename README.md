# Autonomous Customer Support AI Employee

A prototype of an AI-assisted customer-support employee. It accepts a support task through a FastAPI endpoint, uses Google Gemini function/tool calling to work with a mock company SQLite database, verifies database changes, and requests human approval for sensitive refund-related actions.

**Repository:** https://github.com/lakshmicharankoppula/autonomous-customer-support-ai-employee

> This is a sandbox/demo project. It does not connect to a real company's systems and does not execute real refunds.

## Features

- FastAPI endpoints for health checks, task execution, pending approvals, and recording approval decisions.
- SQLite tools for looking up customers, orders, tickets, and refunds.
- Gemini function/tool calling for selecting and sequencing supported tools.
- Verification of tool results before the agent reports that a change succeeded.
- Guardrails to prevent the agent from claiming a refund or logistics action occurred when no such integration exists.
- Human approval requests for refund-related tasks.
- Ticket/refund consistency handling: a refund-related ticket can be reopened when its status is `Resolved` but its refund is not recorded as completed.

## Architecture

```text
User / API client
       |
       v
FastAPI app (app/main.py)
       |
       v
Agent loop (agent/agent_loop.py) <----> Google Gemini API
       |
       +----> Database tools (tools/database_tools.py) ----> SQLite (database/company.db)
       |
       +----> In-memory human approval queue
       |
       v
Grounded task response / verified action summary
```

### Main components

- `app/main.py`: HTTP endpoints and request/response models.
- `agent/agent_loop.py`: agent loop, Gemini tool definitions, safety checks, tool execution, approval queue, and final response construction.
- `agent/baseline_agent.py`: simpler baseline implementation retained for reference.
- `tools/database_tools.py`: parameterized SQLite queries and ticket/order/refund operations.
- `database/company.db`: mock company data for the demo.
- `database/setup_database.py`: database setup/seed script.
- `tests/`: guardrail and ticket/refund consistency tests.

## Setup and run (Windows / Git Bash)

Prerequisites: Python 3.11+ and an internet connection for Gemini API calls.

1. Clone the repository or extract the project ZIP.
2. From the project directory, create and activate a virtual environment:

   ```bash
   python -m venv venv
   source venv/Scripts/activate
   ```

3. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Create a local `.env` file based on `.env.example` and add your own Gemini API key:

   ```dotenv
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-3.1-flash-lite
   ```

   Keep `.env` private. Never commit an API key or use company credentials.

5. Start the API:

   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
   ```

6. Open `http://127.0.0.1:8080/docs` for interactive API documentation. Check `GET /health` first.

### Main endpoints

- `GET /` — service information.
- `GET /health` — health check.
- `POST /execute-task` — submit a natural-language support task.
- `GET /approvals/pending` — list in-memory pending approval requests.
- `POST /approvals/{approval_id}/decision` — record a human decision. Recording a decision does not execute a refund.

## Example demo task

Submit this JSON body to `POST /execute-task` in Swagger UI:

```json
{
  "task": "Find ticket T1004 and its linked order. Check the recorded refund status. If a refund requires approval, create a human approval request. Do not process or claim to process any refund."
}
```

Expected behavior with the included sample data: the agent looks up ticket `T1004`, order `O1004`, and refund `R001`; identifies that approval is pending; creates a human approval request; and clearly states that no financial action was executed. The ticket/refund consistency behavior should prevent a refund-pending ticket from remaining resolved after the relevant update path runs. The actual live result depends on the local database state and Gemini API availability.

## Tests

Run the focused database regression tests:

```bash
python -m unittest tests.test_ticket_refund_consistency -v
```

Run the full test suite:

```bash
python -m unittest discover -s tests -v
```

The agent tests require installed dependencies. Live Gemini execution requires a valid API key, network access, and available API quota. Do not interpret a local unit-test pass as proof that a live Gemini call has succeeded.

## Models, APIs, frameworks, and external components

- **Language model:** Google Gemini, configured through `GEMINI_MODEL`; default in the code is `gemini-3.1-flash-lite`.
- **Model API/SDK:** Google Gen AI Python SDK (`google-genai`) using function/tool calling.
- **HTTP API framework:** FastAPI, served by Uvicorn.
- **Data storage:** SQLite through Python's standard `sqlite3` module.
- **Configuration:** environment variables loaded from `.env` using `python-dotenv`.
- **Validation:** Pydantic request/response models where defined by the FastAPI app.
- **AI coding assistance:** ChatGPT was used during implementation and debugging; the submitted source code and design should be understood and explainable by the author.

## Important technical and design decisions

1. **Tool calling rather than unrestricted database access:** the model chooses from explicitly declared tools; database operations are implemented in Python.
2. **Parameterized SQL:** query values are passed as parameters rather than interpolated into SQL strings.
3. **Verification before claims:** the agent checks tool results before reporting that an update succeeded.
4. **Human approval for sensitive actions:** the system records an approval request rather than executing a financial transaction.
5. **Mock/local data:** SQLite sample records make the prototype demonstrable without access to real customer data or company systems.
6. **Conservative action reporting:** the agent must not claim that a refund or logistics operation happened unless a real integration confirms it.

## Assumptions

- The SQLite database represents a mock support environment and is the source of truth for this prototype.
- Refund status `Pending Approval` means a human decision is still required.
- A recorded approval decision is not equivalent to executing a refund.
- The prototype is operated locally by a trusted developer; production-grade authentication and authorization are not implemented.
- Sample ticket/order/refund identifiers are demonstration data, not real customer records.

## Known limitations

- No real payment/refund processor or logistics provider is integrated; no financial action is executed.
- Approval requests are held in process memory and are lost when the API process restarts.
- Authentication, authorization, audit retention, rate limiting, and production observability are not implemented.
- Gemini behavior depends on API availability, credentials, quota, model access, and network connectivity.
- The prototype has limited retry/error recovery and is not production-ready.
- A local automated test pass does not guarantee end-to-end behavior with the live model.

## What I would build next

1. Persist approval requests and decisions in SQLite or a dedicated database, with an audit trail.
2. Add authentication and role-based authorization for approval endpoints.
3. Add integration tests using a deterministic/mock model, plus controlled end-to-end tests against Gemini.
4. Add idempotency, structured logging, retries/timeouts, and better API error reporting.
5. Integrate a sandbox refund provider only after adding authorization, approval enforcement, and transaction reconciliation.
6. Add monitoring and evaluation for tool-selection accuracy, grounded responses, and guardrail violations.

## Demo video / live demo

This repository provides a locally runnable demo rather than a hosted public service. Record a short screen capture following `DEMO_SCRIPT.md`, then add the resulting accessible video URL here before submission:

**Demo video:** _Add your uploaded video link here._

Do not publish your `.env` file, API key, or any private credentials in the recording.
