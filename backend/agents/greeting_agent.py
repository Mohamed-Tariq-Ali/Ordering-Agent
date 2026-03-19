from backend.utils.llm import chat_completion

GREETING_SYSTEM_PROMPT = """You are a friendly assistant for an online order booking system called "OrderBot".

When greeting users, be warm and welcoming. Briefly mention what you can help with:
- Browse products and check prices
- Place orders (e.g., "Book 2 units of Choco")
- Check order status
- Cancel orders

Keep it short, friendly, and inviting. Use 1-2 emojis max.
"""


def handle_greeting(message: str, conversation_history: list) -> str:
    history = conversation_history[-4:] if len(conversation_history) > 4 else conversation_history
    messages = history + [{"role": "user", "content": message}]
    return chat_completion(messages, GREETING_SYSTEM_PROMPT, temperature=0.7)
