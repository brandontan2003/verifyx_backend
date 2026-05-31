from abc import ABC, abstractmethod


class AIProvider(ABC):
    """
    Abstract base for all AI authentication.
    Every provider must implement the three core operations.
    Prompt templates live in client.py and are passed in as strings —
    authentication are responsible only for calling their model and returning raw text.
    """

    @abstractmethod
    async def complete(self, system: str, user: str, max_tokens: int) -> str:
        """Send a system + user prompt, return the raw text response."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name for logging."""
        ...
