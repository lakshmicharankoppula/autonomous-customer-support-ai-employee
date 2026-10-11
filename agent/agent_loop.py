import os
import re
import time
import uuid
import threading
from contextvars import ContextVar
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from tools.database_tools import (
    search_customer,
    get_order,
    get_ticket,
    update_ticket,
    resolve_ticket,
    get_refund,
)

# ============================================================
# SETUP
# ============================================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY not found. Check your .env file.")

client = genai.Client(api_key=API_KEY)
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# Each request gets its own ledger so concurrent API requests do not
# accidentally share tool results.
RUN_LEDGER: ContextVar[list] = ContextVar("RUN_LEDGER", default=[])

# In-process approval queue for this prototype. Pending approvals are not
# financial execution; this app has no refund-processing integration. For a
# multi-worker deployment, move this store to a shared persistent database.
_APPROVAL_LOCK = threading.Lock()
_PENDING_APPROVALS: dict[str, dict[str, Any]] = {}

def list_pending_approvals() -> list[dict[str, Any]]:
    with _APPROVAL_LOCK:
        return [dict(item) for item in _PENDING_APPROVALS.values() if item["status"] == "pending"]

def decide_approval(approval_id: str, approved: bool, reviewer: str = "api reviewer") -> dict[str, Any] | None:
    with _APPROVAL_LOCK:
        item = _PENDING_APPROVALS.get(approval_id)
        if not item:
            return None
        if item["status"] != "pending":
            return dict(item)
        item["status"] = "approved" if approved else "rejected"
        item["reviewer"] = reviewer[:100]
        item["decided_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return dict(item)


def record_event(tool: str, result: dict) -> None:
    ledger = RUN_LEDGER.get()
    ledger.append({"tool": tool, "result": result})


# ============================================================
# DATABASE TOOL IMPLEMENTATIONS
# ============================================================

def search_customer_tool(name: str) -> dict:
    rows = search_customer(name)
    result = {
        "found": bool(rows),
        "customers": [
            {"customer_id": row[0], "name": row[1], "email": row[2]}
            for row in (rows or [])
        ],
    }
    record_event("search_customer", result)
    return result


def get_order_tool(order_id: str) -> dict:
    row = get_order(order_id)
    if not row:
        result = {"found": False, "order_id": order_id}
    else:
        result = {
            "found": True,
            "order_id": row[0],
            "customer_id": row[1],
            "amount": row[2],
            "status": row[3],
            "delivery_date": row[4],
        }
    record_event("get_order", result)
    return result


def get_ticket_tool(ticket_id: str) -> dict:
    row = get_ticket(ticket_id)
    if not row:
        result = {"found": False, "ticket_id": ticket_id}
    else:
        result = {
            "found": True,
            "ticket_id": row[0],
            "customer_id": row[1],
            "order_id": row[2],
            "subject": row[3],
            "description": row[4],
            "status": row[5],
            "priority": row[6],
            "response": row[7],
        }
    record_event("get_ticket", result)
    return result


# No logistics-escalation or refund-processing integration exists in this
# prototype. Block customer-facing messages that claim either action occurred.
UNSUPPORTED_ACTION_PATTERNS = [
    # Catch variants such as "processed a 10% refund", "issued a refund",
    # and "credited the 450 refund".
    re.compile(
        r"\b(?:i|we)\s+(?:have\s+)?(?:successfully\s+)?"
        r"(?:processed|issued|sent|completed|initiated|credited)\s+"
        r"(?:(?:a|the)\s+)?(?:(?:\d+(?:\.\d+)?%?)\s+)?refund\b",
        re.I,
    ),
    re.compile(
        r"\brefund\b.{0,50}\b(?:has been|was)\s+"
        r"(?:processed|issued|sent|completed|initiated|credited)\b",
        re.I,
    ),
    re.compile(r"\b(?:i|we)\s+(?:have\s+)?(?:escalated|contacted)\b", re.I),
    re.compile(r"\b(?:has been|was)\s+escalated\b", re.I),
    re.compile(
        r"\b(?:i|we)\s+(?:have\s+)?(?:forwarded|submitted)\s+"
        r"(?:this|your order|the order)\s+to\s+(?:the\s+)?"
        r"(?:logistics|delivery)\b",
        re.I,
    ),
    re.compile(
        r"\byou will receive\s+(?:a\s+)?"
        r"(?:status|delivery|refund)\s+(?:update|confirmation)\b",
        re.I,
    ),
]


def unsupported_claim(response: str) -> str | None:
    for pattern in UNSUPPORTED_ACTION_PATTERNS:
        match = pattern.search(response or "")
        if match:
            return (
                "Response rejected because it appears to claim an external action "
                f"that this prototype cannot perform or verify: {match.group(0)!r}. "
                "Rewrite the message to state only verified facts and avoid promising "
                "an escalation, refund, or future update."
            )
    return None


def update_ticket_tool(ticket_id: str, response: str) -> dict:
    problem = unsupported_claim(response)
    if problem:
        result = {
            "success": False,
            "verified": False,
            "ticket_id": ticket_id,
            "error": problem,
        }
        record_event("update_ticket", result)
        return result

    try:
        update_ticket(ticket_id, response)
        row = get_ticket(ticket_id)
        if row and row[7] == response:
            result = {
                "success": True,
                "verified": True,
                "ticket_id": ticket_id,
                "status": row[5],
                "response": row[7],
            }
        else:
            result = {
                "success": False,
                "verified": False,
                "ticket_id": ticket_id,
                "error": "Ticket update could not be verified by reading it back.",
            }
    except Exception as exc:
        result = {
            "success": False,
            "verified": False,
            "ticket_id": ticket_id,
            "error": str(exc),
        }

    record_event("update_ticket", result)
    return result


def resolve_ticket_tool(ticket_id: str) -> dict:
    """Only resolve a ticket when the linked issue is demonstrably complete."""
    try:
        ticket = get_ticket(ticket_id)
        if not ticket:
            result = {"success": False, "verified": False, "error": "Ticket not found."}
            record_event("resolve_ticket", result)
            return result

        subject = str(ticket[3] or "").lower()
        order_id = ticket[2]

        description = str(ticket[4] or "").lower()
        ticket_text = f"{subject} {description}"
        if order_id:
            order = get_order(order_id)
            if not order:
                result = {
                    "success": False, "verified": False, "ticket_id": ticket_id,
                    "status": ticket[5],
                    "error": "Ticket cannot be resolved because its linked order could not be verified.",
                }
                record_event("resolve_ticket", result)
                return result
            order_status = str(order[3] or "").strip().lower()
            if order_status in {"delayed", "shipped", "cancelled", "processing", "pending", "returned", "failed"}:
                result = {
                    "success": False, "verified": False, "ticket_id": ticket_id,
                    "status": ticket[5],
                    "error": (
                        f"Ticket cannot be resolved while linked order status is {order[3]}. "
                        "The underlying order issue is not verified as complete."
                    ),
                }
                record_event("resolve_ticket", result)
                return result

        refund_related = any(term in ticket_text for term in ("refund", "reimbursement", "money back", "return payment"))
        if refund_related:
            refund = get_refund(ticket_id)
            if not refund or str(refund[4]).strip().lower() not in {
                "processed", "completed", "successful", "succeeded"
            }:
                result = {
                    "success": False,
                    "verified": False,
                    "ticket_id": ticket_id,
                    "status": ticket[5],
                    "error": (
                        "Ticket cannot be resolved because no completed refund "
                        "is recorded for this refund request."
                    ),
                }
                record_event("resolve_ticket", result)
                return result

        resolve_ticket(ticket_id)
        updated = get_ticket(ticket_id)
        if updated and str(updated[5]).lower() == "resolved":
            result = {
                "success": True,
                "verified": True,
                "ticket_id": ticket_id,
                "status": updated[5],
            }
        else:
            result = {
                "success": False,
                "verified": False,
                "ticket_id": ticket_id,
                "error": "Ticket resolution could not be verified.",
            }
    except Exception as exc:
        result = {
            "success": False,
            "verified": False,
            "ticket_id": ticket_id,
            "error": str(exc),
        }

    record_event("resolve_ticket", result)
    return result


def get_refund_tool(ticket_id: str) -> dict:
    row = get_refund(ticket_id)
    if not row:
        result = {"found": False, "ticket_id": ticket_id}
    else:
        result = {
            "found": True,
            "refund_id": row[0],
            "ticket_id": row[1],
            "order_id": row[2],
            "amount": row[3],
            "status": row[4],
        }
    record_event("get_refund", result)
    return result


def request_human_approval_tool(reason: str, amount: float) -> dict:
    """Create a pending approval request; never block on terminal input."""
    try:
        numeric_amount = float(amount)
    except (TypeError, ValueError):
        numeric_amount = -1
    if numeric_amount < 0 or not (numeric_amount < float("inf")):
        result = {"approved": False, "status": "rejected", "error": "Invalid approval amount."}
        record_event("request_human_approval", result)
        return result
    approval_id = str(uuid.uuid4())
    item = {
        "approval_id": approval_id,
        "reason": str(reason)[:1000],
        "amount_inr": round(numeric_amount, 2),
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "message": "Approval is pending. No financial action has been executed.",
    }
    with _APPROVAL_LOCK:
        _PENDING_APPROVALS[approval_id] = item
    result = {
        "approved": False,
        "status": "pending",
        "approval_id": approval_id,
        "amount_inr": item["amount_inr"],
        "message": item["message"],
    }
    record_event("request_human_approval", result)
    return result


FUNCTIONS = {
    "search_customer": search_customer_tool,
    "get_order": get_order_tool,
    "get_ticket": get_ticket_tool,
    "update_ticket": update_ticket_tool,
    "resolve_ticket": resolve_ticket_tool,
    "get_refund": get_refund_tool,
    "request_human_approval": request_human_approval_tool,
}

# ============================================================
# GEMINI TOOL DEFINITIONS
# ============================================================

def string_property(description: str) -> types.Schema:
    return types.Schema(type=types.Type.STRING, description=description)


def object_schema(properties: dict, required: list[str]) -> types.Schema:
    return types.Schema(
        type=types.Type.OBJECT,
        properties=properties,
        required=required,
    )


gemini_tools = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="search_customer",
            description="Search for a customer by name.",
            parameters=object_schema(
                {"name": string_property("Customer name")},
                ["name"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_order",
            description="Read the recorded details and status of an order.",
            parameters=object_schema(
                {"order_id": string_property("Order ID, such as O1002")},
                ["order_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_ticket",
            description="Read a support ticket, including its recorded status and response.",
            parameters=object_schema(
                {"ticket_id": string_property("Ticket ID, such as T1002")},
                ["ticket_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="update_ticket",
            description=(
                "Write a customer-facing response to a ticket. The tool rejects "
                "claims of refunds, logistics escalations, or future updates that "
                "this prototype cannot perform or verify."
            ),
            parameters=object_schema(
                {
                    "ticket_id": string_property("Ticket ID"),
                    "response": string_property(
                        "Customer response containing only verified facts"
                    ),
                },
                ["ticket_id", "response"],
            ),
        ),
        types.FunctionDeclaration(
            name="resolve_ticket",
            description=(
                "Resolve a ticket only if the underlying issue is demonstrably "
                "complete. The tool refuses resolution for delayed/shipped orders "
                "and refund requests without a recorded completed refund."
            ),
            parameters=object_schema(
                {"ticket_id": string_property("Ticket ID")},
                ["ticket_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_refund",
            description="Check the recorded refund, if any, for a support ticket.",
            parameters=object_schema(
                {"ticket_id": string_property("Ticket ID")},
                ["ticket_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="request_human_approval",
            description=(
                "Request explicit human approval for a proposed financial action. "
                "Approval is not execution: this prototype has no refund-processing "
                "tool, so do not claim a refund was processed even if approved."
            ),
            parameters=object_schema(
                {
                    "reason": string_property("Why approval is required"),
                    "amount": types.Schema(
                        type=types.Type.NUMBER,
                        description="Amount in Indian rupees (INR)",
                    ),
                },
                ["reason", "amount"],
            ),
        ),
    ]
)

# ============================================================
# GEMINI CALL WITH RETRY
# ============================================================

def call_gemini(contents):
    for attempt in range(3):
        try:
            print(f"[LLM] Attempt {attempt + 1}/3")
            return client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=[gemini_tools],
                    temperature=0.1,
                    system_instruction=(
                        "You are a careful autonomous customer-support agent. "
                        "Use only tool results as evidence. Amounts are in INR. "
                        "This application can read/update tickets and read orders/refunds, "
                        "but it cannot process refunds or contact/escalate to logistics. "
                        "Never claim an action occurred unless a tool result verifies it. "
                        "Human approval only authorizes a proposal; it does not execute "
                        "a refund. If approval is rejected, do not retry or perform that "
                        "financial action. Never resolve an issue while its order is "
                        "delayed/shipped or a requested refund is not recorded as completed. "
                        "Report the actual status returned by the database. If unable to "
                        "complete the task, say exactly what remains pending."
                    ),
                ),
            )
        except Exception as exc:
            error_text = str(exc)
            print(f"[LLM ERROR] Attempt {attempt + 1}: {error_text}")
            retryable = any(
                token in error_text.upper()
                for token in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")
            )
            if retryable and attempt < 2:
                wait_seconds = 3 * (attempt + 1)
                print(f"[LLM] Temporary/rate-limit failure; retrying in {wait_seconds}s.")
                time.sleep(wait_seconds)
                continue
            raise


# ============================================================
# GROUNDED FINAL SUMMARY
# ============================================================

def build_grounded_summary(task: str, ledger: list[dict[str, Any]]) -> dict:
    """Build the API result from tool outputs rather than trusting free-form claims."""
    tool_events = [event for event in ledger if isinstance(event, dict)]
    updates = [
        event["result"] for event in tool_events
        if event.get("tool") == "update_ticket"
    ]
    resolutions = [
        event["result"] for event in tool_events
        if event.get("tool") == "resolve_ticket"
    ]
    approvals = [
        event["result"] for event in tool_events
        if event.get("tool") == "request_human_approval"
    ]
    orders = [
        event["result"] for event in tool_events
        if event.get("tool") == "get_order" and event["result"].get("found")
    ]
    tickets = [
        event["result"] for event in tool_events
        if event.get("tool") == "get_ticket" and event["result"].get("found")
    ]
    refunds = [
        event["result"] for event in tool_events
        if event.get("tool") == "get_refund"
    ]

    verified_updates = [item for item in updates if item.get("success") and item.get("verified")]
    verified_resolutions = [
        item for item in resolutions if item.get("success") and item.get("verified")
    ]
    rejected = any(item.get("status") == "rejected" or item.get("approved") is False and item.get("status") != "pending" for item in approvals)
    approved = any(item.get("status") == "approved" or item.get("approved") is True for item in approvals)
    approval_pending = any(item.get("status") == "pending" for item in approvals)

    facts = []
    if orders:
        order = orders[-1]
        facts.append(
            f"Order {order['order_id']} is recorded as {order['status']} "
            f"(order value ₹{float(order['amount']):,.2f})."
        )

    # Derive the most recent ticket status from every tool result that reports it,
    # including update/resolve operations, rather than relying on an earlier read.
    status_observations = []
    for event in tool_events:
        tool_name = event.get("tool")
        result = event.get("result", {})
        if result.get("found") and tool_name == "get_ticket" and result.get("status"):
            status_observations.append((result["ticket_id"], result["status"]))
        elif tool_name == "update_ticket" and result.get("status"):
            status_observations.append((result.get("ticket_id"), result["status"]))
        elif tool_name == "resolve_ticket" and result.get("status"):
            status_observations.append((result.get("ticket_id"), result["status"]))
    if status_observations:
        ticket_id, status = status_observations[-1]
        facts.append(f"Ticket {ticket_id} status is recorded as {status}.")
    if verified_updates:
        update = verified_updates[-1]
        facts.append(f"Ticket {update['ticket_id']} response was updated and verified.")
    elif updates:
        facts.append("The attempted ticket response update was not verified.")
    if approvals:
        if rejected:
            facts.append("Human approval for the proposed financial action was rejected.")
        elif approved:
            facts.append("Human approval was granted, but approval alone did not execute a refund.")
        elif approval_pending:
            facts.append("A human approval request was created and is awaiting a decision.")
    if refunds:
        refund = refunds[-1]
        if refund.get("found"):
            facts.append(
                f"Refund {refund.get('refund_id')} is recorded with status "
                f"{refund.get('status')}."
            )
        else:
            facts.append("No refund record was found for the checked ticket.")
    if verified_resolutions:
        facts.append(f"Ticket {verified_resolutions[-1]['ticket_id']} resolution was verified.")
    elif resolutions:
        facts.append("Ticket resolution was not completed because the tool did not verify it.")

    pending = []
    if orders and str(orders[-1].get("status", "")).lower() in {"delayed", "shipped"}:
        pending.append("The order issue remains unresolved in the order system.")
    if rejected:
        pending.append("The rejected financial action was not performed.")
    elif approved:
        pending.append("No refund-processing integration exists in this prototype.")
    elif approval_pending:
        pending.append("Human approval is pending; no financial action was executed.")
    if not verified_updates:
        pending.append("A verified customer-facing ticket update has not been confirmed.")

    summary = " ".join(facts) if facts else "The available tools did not return enough verified information."
    if pending:
        summary += " Pending: " + " ".join(pending)

    # Task execution success is distinct from business-issue resolution.
    # A pending human approval can mean the requested workflow step succeeded;
    # it does not mean that the refund itself was executed.
    task_lower = task.lower()
    asks_update = any(term in task_lower for term in (
        "update the ticket", "update ticket", "update the response",
        "write a response", "respond to the ticket", "customer-facing response",
    ))
    asks_resolve = any(term in task_lower for term in (
        "resolve the ticket", "resolve ticket", "close the ticket", "close ticket",
    ))
    refund_action_terms = (
        "process the refund", "process any refund", "issue the refund",
        "issue any refund", "refund the customer", "execute refund",
        "execute the refund",
    )
    explicitly_forbids_refund_execution = bool(re.search(
        r"\b(?:do not|don't|dont|never|must not|should not)\s+"
        r"(?:actually\s+)?(?:process|issue|execute)\b.{0,60}\brefund\b",
        task_lower,
    ))
    asks_refund_action = (
        any(term in task_lower for term in refund_action_terms)
        and not explicitly_forbids_refund_execution
    )
    asks_approval = any(term in task_lower for term in (
        "approval", "approve", "human review", "human approval",
    ))

    has_verified_read = bool(
        orders
        or tickets
        or any(
            event.get("tool") == "search_customer"
            and event.get("result", {}).get("found")
            for event in tool_events
        )
        or any(item.get("found") for item in refunds)
    )
    approval_request_created = any(
        item.get("approval_id") and item.get("status") in {"pending", "approved", "rejected"}
        for item in approvals
    )

    success = has_verified_read or bool(verified_updates) or bool(verified_resolutions)

    # Requested writes/resolution require verification, not merely a model claim.
    if asks_update and not verified_updates:
        success = False
    if asks_resolve and not verified_resolutions:
        success = False

    # There is deliberately no refund execution integration in this prototype.
    # Human approval is not equivalent to executing the financial transaction.
    if asks_refund_action:
        success = False

    # An explicit request to create/seek approval is successful when the approval
    # record was actually created, even though the financial action remains pending.
    if asks_approval and approval_request_created and not asks_refund_action:
        success = True

    # A rejected proposal is not successful when the user requested the action.
    # A merely pending approval, however, must not erase successful lookup/request work.
    if rejected:
        success = False

    if orders and str(orders[-1].get("status", "")).lower() in {
        "delayed", "shipped", "cancelled", "processing", "pending", "returned", "failed"
    }:
        # A read-only lookup may succeed while the underlying business issue remains open.
        # Tasks that ask for an update or resolution of that issue remain incomplete.
        if asks_update or asks_resolve or asks_refund_action:
            success = False

    return {
        "success": success,
        "task": task,
        "final_response": summary,
        "verified_actions": {
            "ticket_updates": verified_updates,
            "ticket_resolutions": verified_resolutions,
        },
        "pending": pending,
    }


# ============================================================
# AGENT LOOP
# ============================================================

def run_agent(task: str) -> dict:
    ledger: list[dict[str, Any]] = []
    token = RUN_LEDGER.set(ledger)

    print("\n================================")
    print("AUTONOMOUS AI EMPLOYEE")
    print("================================")
    print("[MODEL]", MODEL)
    print("[TASK]", task)

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part(
                    text=f"""
Task:
{task}

Operating rules:
1. Investigate the customer, relevant ticket, order, and refund records using tools.
2. Use actual tool results; do not invent or assume facts.
3. Update the ticket with a truthful, professional response when appropriate.
4. This prototype has NO tool for processing refunds and NO tool for contacting or escalating to logistics.
5. Never claim a refund was processed, a logistics escalation happened, or a future update was scheduled.
6. Amounts are in Indian rupees (INR).
7. Financial actions require human approval, but approval does not execute a refund.
8. If approval is rejected, do not perform the proposed financial action.
9. Do not resolve a ticket while the order issue remains delayed/shipped or a refund request has no completed refund record.
10. A successful tool result must be checked; if a tool rejects an action, adapt without repeating the unsupported action.
11. At the end, give a concise summary based only on verified tool results. Do not contradict the database.
""",
                )
            ],
        )
    ]

    try:
        for step in range(10):
            print(f"\n[AGENT STEP {step + 1}]")
            try:
                response = call_gemini(contents)
            except Exception as exc:
                print("[LLM ERROR]", exc)
                return {
                    "success": False,
                    "task": task,
                    "error": "Language model request failed. Check server logs for details.",
                    "final_response": "The task could not be completed because the language model request failed.",
                    "tool_history": ledger,
                }

            if not response.candidates:
                return {
                    "success": False,
                    "task": task,
                    "error": "Gemini returned no candidates.",
                    "final_response": "The model returned no response.",
                    "tool_history": ledger,
                }

            model_content = response.candidates[0].content
            function_calls = [
                part.function_call
                for part in (model_content.parts or [])
                if getattr(part, "function_call", None)
            ]

            if not function_calls:
                # Do not return unverified model-generated prose. Build the final
                # report from recorded tool outputs instead.
                result = build_grounded_summary(task, ledger)
                print("\n[AGENT] GROUNDED FINAL RESPONSE")
                print(result["final_response"])
                result["tool_history"] = ledger
                return result

            contents.append(model_content)
            tool_response_parts = []

            for call in function_calls:
                function_name = call.name
                arguments = dict(call.args or {})
                print(f"\n[TOOL] {function_name}")
                print("[ARGS]", arguments)

                function = FUNCTIONS.get(function_name)
                if function is None:
                    tool_result = {
                        "success": False,
                        "error": f"Unknown tool: {function_name}",
                    }
                else:
                    try:
                        tool_result = function(**arguments)
                    except Exception as exc:
                        print(f"[TOOL ERROR] {function_name}: {type(exc).__name__}: {exc}")
                        tool_result = {"success": False, "error": "Tool execution failed. Check server logs for details."}
                        record_event(function_name, tool_result)

                print("[RESULT]", tool_result)
                tool_response_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=function_name,
                            response=tool_result,
                        )
                    )
                )

            contents.append(
                types.Content(role="user", parts=tool_response_parts)
            )

        result = build_grounded_summary(task, ledger)
        result["success"] = False
        result["error"] = "Agent reached maximum number of steps."
        result["final_response"] += " The agent stopped after reaching its step limit."
        result["tool_history"] = ledger
        return result
    finally:
        RUN_LEDGER.reset(token)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    task_text = input("\nEnter customer support task: ").strip()
    if not task_text:
        print("No task provided.")
    else:
        print("\n================================")
        print("FINAL RESULT")
        print("================================")
        print(run_agent(task_text))
