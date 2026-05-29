from app.dto.base import BaseDTO


class RetrieveThemeResponse(BaseDTO):
    theme: list[str]
