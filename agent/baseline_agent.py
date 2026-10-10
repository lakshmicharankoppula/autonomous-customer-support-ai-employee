print("AGENT FILE STARTED")

from tools.database_tools import (
    search_customer,
    get_order,
    get_ticket,
    update_ticket,
    resolve_ticket,
)


def handle_delayed_order(ticket_id):
    print(f"\n[AGENT] Starting task for ticket {ticket_id}")

    # 1. Get ticket
    ticket = get_ticket(ticket_id)
    print("[AGENT] Ticket:", ticket)

    if ticket is None:
        print("[AGENT] Ticket not found.")
        return {"success": False, "reason": "Ticket not found"}

    # Ticket structure:
    # 0 = ticket_id
    # 1 = customer_id
    # 2 = order_id
    # 3 = subject
    # 4 = description
    # 5 = status
    # 6 = priority
    # 7 = response

    order_id = ticket[2]
    customer_id = ticket[1]

    # 2. Get customer
    customer_results = search_customer("Priya")

    if not customer_results:
        print("[AGENT] Customer not found.")
        return {"success": False, "reason": "Customer not found"}

    customer = customer_results[0]
    print("[AGENT] Customer:", customer)

    # Customer structure:
    # 0 = customer_id
    # 1 = name
    # 2 = email

    # 3. Get order
    order = get_order(order_id)

    if order is None:
        print("[AGENT] Order not found.")
        return {"success": False, "reason": "Order not found"}

    print("[AGENT] Order:", order)

    # Order structure:
    # 0 = order_id
    # 1 = customer_id
    # 2 = amount
    # 3 = status
    # 4 = delivery_date

    order_status = order[3]
    customer_name = customer[1]

    print("[AGENT] Order status:", order_status)

    # 4. Decide action
    if order_status == "Delayed":

        response = (
            f"Hello {customer_name}, your order {order_id} "
            "is currently delayed. We apologize for the delay "
            "and are working to get it delivered as soon as possible."
        )

        print("[AGENT] Decision: Update ticket")

        # 5. Execute action
        update_ticket(ticket_id, response)

        print("[AGENT] Ticket updated.")

    else:
        response = (
            f"Hello {customer_name}, your order {order_id} "
            f"is currently {order_status}."
        )

        update_ticket(ticket_id, response)

        print("[AGENT] Ticket updated.")

    # 6. Verify
    print("[AGENT] Verifying result...")

    updated_ticket = get_ticket(ticket_id)

    if updated_ticket is None:
        print("[VERIFY] FAILED - ticket disappeared")
        return {"success": False}

    # Response is index 7
    saved_response = updated_ticket[7]

    if saved_response == response:
        print("[VERIFY] SUCCESS")

        result = {
            "success": True,
            "ticket_id": ticket_id,
            "customer": customer_name,
            "order_id": order_id,
            "order_status": order_status,
            "action": "Ticket updated",
            "evidence": saved_response,
        }

        print("\n[AGENT] FINAL RESULT")
        print(result)

        return result

    print("[VERIFY] FAILED - response mismatch")

    return {
        "success": False,
        "reason": "Verification failed",
    }


if __name__ == "__main__":
    result = handle_delayed_order("T1002")