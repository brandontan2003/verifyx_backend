from app.dto.code import RetrieveThemeResponse
from app.enums.ThemeEnum import QuestionTheme


def retrieve_theme() -> list[str]:
    return [theme.value for theme in QuestionTheme]


def retrieve_theme_service() -> RetrieveThemeResponse:
    theme = retrieve_theme()
    return RetrieveThemeResponse(theme=theme)
