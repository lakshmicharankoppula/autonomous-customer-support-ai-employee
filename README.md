# Autonomous Customer Support AI Employee

An agentic customer-support prototype using Gemini tool calling and a SQLite company database to investigate customer issues, update support tickets, verify database changes, and request human approval for sensitive financial actions.

> **Prototype limitation:** This is a simulated company environment. It does not connect to a payment gateway, email provider, or logistics platform. It cannot actually process refunds or contact/escalate to logistics.

## Features

- Natural-language task input
- Gemini-powered tool selection and multi-step execution
- SQLite-backed customer, order, ticket, and refund lookups
- Ticket-response updates with read-back verification
- Guardrails against claiming unsupported refund or logistics actions
- Human approval prompt for proposed financial actions
- Tool history and a final summary based on recorded tool results
- FastAPI endpoint and interactive Swagger documentation

## Architecture

```text
User task
   |
   v
FastAPI endpoint / CLI
   |
   v
Gemini agent loop
   | selects tools
   v
Tool implementations
   +--> Customer lookup
   +--> Order lookup
   +--> Ticket lookup / update / resolution
   +--> Refund lookup
   +--> Human approval prompt
   |
   v
SQLite company database
   |
   v
Read-back verification + grounded task summary
```

## Main components

- `agent/agent_loop.py` — Gemini tool definitions, agent loop, guardrails, approval prompt, and task summary.
- `agent/baseline_agent.py` — deterministic baseline workflow used during development.
- `app/main.py` — FastAPI application and task-execution endpoint.
- `tools/database_tools.py` — SQLite operations used by the agent.
- `database/setup_database.py` — creates and populates the sample company database.
- `database/company.db` — local SQLite database created by the setup script.
- `tests/` — location for automated tests.

## Requirements

- Python 3.10 or newer recommended
- A Gemini API key
- Internet access for Gemini API requests

Commands below assume Windows PowerShell opened in the project root.

## Setup

### 1. Create and activate a virtual environment

If the project already has a working `venv`, activate it instead of creating another one.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.1-flash-lite
```

Keep `.env` private. Never commit the API key to GitHub.

### 4. Initialize the sample database

```powershell
python database/setup_database.py
```

**Warning:** Running the setup script may recreate or reset sample data, depending on its implementation. Back up `database/company.db` first if you need to preserve current ticket changes.

## Run the application

### Start the API

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Keep the terminal running.

### Open Swagger

Visit `http://127.0.0.1:8000/docs`.

Use `POST /execute-task` with a JSON body such as:

```json
{
  "task": "Check Priya's delayed order and update her support ticket"
}
```

The API also exposes `GET /`, which reports whether the application is running.

### Run the agent from the command line

```powershell
python -m agent.agent_loop
```

Enter a customer-support task when prompted.

## Example tasks

```text
Check Priya's delayed order and update her support ticket.
Look up order O1003 and summarize its recorded status.
Check whether a refund is recorded for ticket T1004.
```

Results depend on the current state of the local database, which may have changed during previous runs.

## Safety and verification approach

- The agent should use tool results rather than invent customer, order, ticket, or refund details.
- Ticket updates are read back from the database to verify that the response was saved.
- Refund approval is not the same as refund execution.
- The prototype has no refund-processing integration.
- The prototype has no logistics escalation integration.
- Ticket resolution should be blocked when the linked delivery issue remains unresolved or a refund request has no recorded completed refund.
- The final task summary is built from recorded tool results rather than relying only on free-form model text.

## Known limitations

1. **Simulated environment:** The database contains sample company records only.
2. **No real refund execution:** The application can inspect refund records and request approval, but cannot issue a payment or refund.
3. **No logistics integration:** The application cannot contact a carrier, escalate an order, or schedule a delivery update.
4. **Console-based approval:** The current human-approval implementation reads from terminal input. Approval-required requests submitted through HTTP may wait for input in the server terminal and are not suitable for a production web workflow.
5. **Model/API dependency:** Agent execution requires a reachable Gemini API and may be affected by rate limits or service availability.
6. **Limited automated evaluation:** Add repeatable tests for successful updates, rejected approval, unsupported claims, missing records, and unresolved orders before treating the system as reliable.
7. **Single local database:** SQLite is suitable for this prototype, not for a concurrent production service without further design work.
8. **No authentication or authorization:** The API is intended for local development and should not be exposed publicly as-is.

## Suggested evaluation cases

| Case | Expected behaviour |
|---|---|
| Customer exists and order is delayed | Retrieve records, provide a truthful ticket response, verify the update, and leave the delivery issue pending |
| Customer or order is missing | Report that the record could not be found; do not invent details |
| Refund record is missing | State that no refund record was found; do not claim a refund was processed |
| Human rejects a financial proposal | Do not perform the proposed financial action |
| Ticket update fails verification | Report failure rather than claiming success |
| Order remains delayed or shipped | Do not mark the underlying issue resolved |
| Refund request has no completed refund | Do not resolve the refund ticket |

## Repository hygiene

Before publishing:

- Confirm `.env`, `venv/`, `__pycache__/`, and local database files are ignored by Git.
- Never commit API keys or other secrets.
- Decide whether the sample database should be regenerated on setup rather than committed.
- Include a sanitized example request and response in the project documentation.
- Add automated tests and document their actual results; do not claim tests passed unless they were run.

## Future improvements

- Replace terminal `input()` approval with a proper approval workflow suitable for HTTP requests.
- Add a real, sandboxed refund provider integration with idempotency and transaction verification.
- Add a logistics integration or a clearly defined escalation tool.
- Add automated unit and integration tests.
- Add structured logs, request IDs, timeouts, and robust retry handling.
- Add authentication, authorization, and audit logging.
- Add an evaluation harness measuring task completion, unsupported-claim rate, tool errors, and verification success.

## Project status

This is a development prototype. The API and agent workflow have been exercised manually during development, but the latest guardrail changes still require end-to-end testing before their behaviour can be considered verified.

## Running Tests

Run the automated guardrail tests from the project root:

```powershell
python -m unittest discover -s tests -v