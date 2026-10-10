from database_tools import (
    search_customer,
    get_customer,
    get_order,
    search_tickets,
    get_ticket,
    update_ticket,
    resolve_ticket,
    get_refund,
)


print("\n===== CUSTOMER SEARCH =====")
print(search_customer("Rahul"))


print("\n===== CUSTOMER =====")
print(get_customer("C001"))


print("\n===== ORDER =====")
print(get_order("O1001"))


print("\n===== OPEN TICKETS =====")
for ticket in search_tickets("Open"):
    print(ticket)


print("\n===== SINGLE TICKET =====")
print(get_ticket("T1001"))


print("\n===== REFUND =====")
print(get_refund("T1004"))
