import pytest

from app.enums.QuestionTypeEnum import QuestionType


class TestQuestionType:
    def test_all_members_present(self):
        members = {m.value for m in QuestionType}
        assert members == {"mcq", "true_false"}

    def test_is_string_enum(self):
        assert isinstance(QuestionType.mcq, str)
        assert QuestionType.mcq == "mcq"

    def test_lookup_by_value(self):
        assert QuestionType("mcq") is QuestionType.mcq
        assert QuestionType("true_false") is QuestionType.true_false

    def test_mcq_not_equal_true_false(self):
        assert QuestionType.mcq != QuestionType.true_false

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            QuestionType("free_text")
