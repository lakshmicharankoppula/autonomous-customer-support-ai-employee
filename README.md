# Autonomous Customer Support AI Employee — Patch

This patch contains the updated Gemini agent loop, FastAPI entry point, and regression tests for the existing project.

## What changed

- Corrected task-success semantics so that a pending approval does not automatically make a successfully executed approval-request task fail.
- Kept the hard guardrail that requests to actually process a refund cannot return success when no refund-processing integration exists.
- Added tests for pending approval workflow and the refund-processing limitation.
- Kept approval decisions separate from financial execution.

## Apply to the existing repository

Copy `agent/agent_loop.py`, `app/main.py`, `tests/test_agent_guardrails.py`, and `requirements.txt` into the matching paths in your existing project. Do not overwrite `.env` or your local database.

See `PATCH_INSTRUCTIONS.md` for exact commands.

## Known limitations

- Gemini API access and a valid local `.env` are required for live agent requests.
- Approval requests are stored in memory and are lost on server restart.
- Approving a request records a human decision only; no refund is executed.
- This prototype is not production-ready and has no authentication or authorization.
