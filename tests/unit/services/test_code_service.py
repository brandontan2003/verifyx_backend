from app.enums.ThemeEnum import QuestionTheme
from app.services.code_service import retrieve_theme, retrieve_theme_service


class TestRetrieveTheme:
    def test_returns_list_of_strings(self):
        result = retrieve_theme()
        assert isinstance(result, list)
        assert all(isinstance(t, str) for t in result)

    def test_contains_all_enum_values(self):
        result = retrieve_theme()
        for theme in QuestionTheme:
            assert theme.value in result

    def test_no_duplicates(self):
        result = retrieve_theme()
        assert len(result) == len(set(result))


class TestRetrieveThemeService:
    def test_returns_retrieve_theme_response_with_themes(self):
        result = retrieve_theme_service()
        assert hasattr(result, "theme")
        assert len(result.theme) > 0

    def test_theme_values_match_retrieve_theme(self):
        result = retrieve_theme_service()
        assert result.theme == retrieve_theme()
