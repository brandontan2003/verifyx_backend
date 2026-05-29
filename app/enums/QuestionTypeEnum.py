import enum


class QuestionType(str, enum.Enum):
    mcq = "mcq"
    true_false = "true_false"
