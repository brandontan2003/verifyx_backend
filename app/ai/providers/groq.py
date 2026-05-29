import httpx

from app.ai.base import AIProvider
from app.config import settings


class GroqProvider(AIProvider):
    """
    Groq-hosted open-source model fallback.
    Groq exposes an OpenAI-compatible /openai/v1/chat/completions endpoint.
    Free tier supports llama-3.3-70b-versatile and mixtral-8x7b-32768.
    Get an API key at: https://console.groq.com
    """

    _BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

    @property
    def name(self) -> str:
        return "groq"

    async def complete(self, system: str, user: str, max_tokens: int) -> str:
        payload = {
            "model": settings.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "max_completion_tokens": max_tokens,
            "temperature": 0.7,
            "stream": False,
            "stop": "```",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self._BASE_URL,
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload
            )
            response.raise_for_status()

        return response.json()["choices"][0]["message"]["content"]
