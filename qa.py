import os

from google import genai
from google.genai import types

from messages import Message

_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

_SYSTEM = (
    "You are a concierge assistant with deep knowledge of a member's history. "
    "You will be given a chronological log of a member's messages. "
    "Read ALL messages carefully before answering — treat them as a connected conversation, not isolated facts. "
    "Reason across the full history: infer connections between implicit references and explicit names "
    "that appear in related context across different messages. "
    "Synthesise a complete answer from the full picture rather than reporting isolated statements. "
    "Be specific — include names, dates, and numbers where relevant. "
    "If the answer genuinely cannot be determined from the messages, say so clearly."
)


async def answer(question: str, member_messages: list[Message]) -> str:
    user_name = member_messages[0].user_name
    history = "\n".join(f"[{m.timestamp[:10]}] {m.message}" for m in member_messages)
    prompt = f"Member: {user_name}\nMessages:\n{history}\n\nQuestion: {question}"
    response = await _client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=_SYSTEM),
    )
    return response.text.strip()
