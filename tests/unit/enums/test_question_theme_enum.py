import pytest

from app.enums.ThemeEnum import QuestionTheme


class TestQuestionTheme:
    def test_all_members_present(self):
        members = {m.value for m in QuestionTheme}
        assert members == {
            "misinformation", "scam", "phishing",
            "crisis", "data privacy", "deepfake", "AI awareness"
        }

    def test_is_string_enum(self):
        assert isinstance(QuestionTheme.SCAM, str)
        assert QuestionTheme.SCAM == "scam"

    def test_lookup_by_value(self):
        assert QuestionTheme("scam") is QuestionTheme.SCAM
        assert QuestionTheme("phishing") is QuestionTheme.PHISHING
        assert QuestionTheme("deepfake") is QuestionTheme.DEEPFAKE
        assert QuestionTheme("data privacy") is QuestionTheme.DATA_PRIVACY
        assert QuestionTheme("AI awareness") is QuestionTheme.AI_AWARENESS

    def test_theme_values_contain_no_duplicates(self):
        values = [m.value for m in QuestionTheme]
        assert len(values) == len(set(values))

    def test_themes_align_with_harm_types(self):
        """Core themes overlap with known online harm categories."""
        themes = {m.value for m in QuestionTheme}
        assert "misinformation" in themes
        assert "scam" in themes
        assert "phishing" in themes
        assert "deepfake" in themes

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            QuestionTheme("hacking")
