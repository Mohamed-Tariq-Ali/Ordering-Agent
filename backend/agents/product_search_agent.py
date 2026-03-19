from backend.utils.llm import chat_completion
from backend.utils.catalog import get_all_products

PRODUCT_SEARCH_SYSTEM_PROMPT = """You are a friendly product search agent for an online store.
Your job is to help users find products, check prices, and explore the catalog.

Be conversational, helpful, and enthusiastic. Format prices nicely.
When listing products, make it easy to read.
Always suggest the user can order something if they're interested.

Current catalog:
{catalog}
"""


def handle_product_search(message: str, conversation_history: list) -> str:
    products = get_all_products()
    catalog_text = "\n".join([
        f"- {p['name']} | ₹{p['price']} per {p['unit']} | Stock: {p['stock']} | {p['description']}"
        for p in products
    ])
    system = PRODUCT_SEARCH_SYSTEM_PROMPT.format(catalog=catalog_text)
    history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
    messages = history + [{"role": "user", "content": message}]
    return chat_completion(messages, system, temperature=0.5)
