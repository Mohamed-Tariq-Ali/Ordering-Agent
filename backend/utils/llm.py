import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_groq_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in .env file")
        _client = Groq(api_key=api_key)
    return _client


def chat_completion(messages: list, system_prompt: str, temperature: float = 0.3) -> str:
    """Call Groq and return the assistant's reply as a string."""
    client = get_groq_client()
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=full_messages,
        temperature=temperature,
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()
