import json
import re
from backend.utils.llm import chat_completion
from backend.utils.catalog import search_product, get_all_products
from backend.utils.order_store import save_order
from backend.models.schemas import Order, OrderItem

ORDER_EXTRACTION_PROMPT = """You are an order extraction agent. Extract order details from the user message.

Available products:
{catalog}

From the user message, extract:
1. Product name(s)
2. Quantity for each product
3. Customer name (if mentioned)

Respond ONLY with valid JSON in this exact format:
{{
  "items": [
    {{"product_name": "Choco", "quantity": 2}},
    {{"product_name": "Cookies", "quantity": 1}}
  ],
  "customer_name": "John" or null,
  "notes": "any special notes" or null
}}

If you cannot extract a clear order, respond with:
{{"items": [], "customer_name": null, "notes": null}}
"""

ORDER_CONFIRM_SYSTEM_PROMPT = """You are a friendly order confirmation agent.
You have just processed an order. Inform the user of:
1. The order ID
2. What was ordered and quantities
3. Total amount
4. That the order is confirmed

Be warm, professional, and concise. Use emojis sparingly.
"""

ORDER_CLARIFY_SYSTEM_PROMPT = """You are a helpful order booking agent.
The user wants to place an order but the details are unclear or the product wasn't found.

Available products:
{catalog}

Ask the user for clarification politely. Help them choose a product from the catalog.
Be conversational and friendly.
"""


def handle_order_booking(message: str, conversation_history: list) -> tuple[str, dict | None]:
    """
    Returns (reply_text, order_dict_or_None)
    """
    products = get_all_products()
    catalog_text = "\n".join([f"- {p['name']} (₹{p['price']}/{p['unit']})" for p in products])

    # Step 1: Extract order details using LLM
    extraction_prompt = ORDER_EXTRACTION_PROMPT.format(catalog=catalog_text)
    history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
    messages = history + [{"role": "user", "content": message}]

    raw = chat_completion(messages, extraction_prompt, temperature=0.1)

    # Parse JSON from LLM response
    extracted = None
    try:
        # Try to find JSON in the response
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            extracted = json.loads(json_match.group())
    except (json.JSONDecodeError, AttributeError):
        extracted = None

    # Step 2: Validate extracted items against real catalog
    if not extracted or not extracted.get("items"):
        # Couldn't extract — ask for clarification
        clarify_prompt = ORDER_CLARIFY_SYSTEM_PROMPT.format(catalog=catalog_text)
        reply = chat_completion(messages, clarify_prompt, temperature=0.5)
        return reply, None

    # Step 3: Build the order
    order_items = []
    not_found = []

    for item in extracted["items"]:
        product = search_product(item["product_name"])
        if not product:
            not_found.append(item["product_name"])
            continue

        qty = max(1, int(item.get("quantity", 1)))
        order_items.append(OrderItem(
            product_id=product["product_id"],
            product_name=product["name"],
            quantity=qty,
            unit_price=product["price"],
            total_price=round(product["price"] * qty, 2)
        ))

    if not order_items:
        # All products not found
        clarify_prompt = ORDER_CLARIFY_SYSTEM_PROMPT.format(catalog=catalog_text)
        messages_with_note = messages + [{
            "role": "system",
            "content": f"Note: Products not found in catalog: {', '.join(not_found)}"
        }]
        reply = chat_completion(messages_with_note, clarify_prompt, temperature=0.5)
        return reply, None

    # Step 4: Create and save order
    total = round(sum(i.total_price for i in order_items), 2)
    order = Order(
        customer_name=extracted.get("customer_name"),
        items=order_items,
        total_amount=total,
        status="confirmed",
        notes=extracted.get("notes")
    )
    save_order(order)

    # Step 5: Generate a friendly confirmation message
    order_summary = f"""
Order ID: {order.order_id}
Items:
{chr(10).join([f'  - {i.product_name} x{i.quantity} = ₹{i.total_price}' for i in order_items])}
Total: ₹{total}
Status: Confirmed
"""
    confirm_messages = [{"role": "user", "content": f"Order placed successfully:\n{order_summary}\n\nGenerate a warm confirmation message for the customer."}]
    reply = chat_completion(confirm_messages, ORDER_CONFIRM_SYSTEM_PROMPT, temperature=0.6)

    return reply, order.model_dump()
