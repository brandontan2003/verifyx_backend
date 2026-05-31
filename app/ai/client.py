import json
import re

from app.ai.factory import complete_with_fallback
from app.config import settings
from app.enums.QuestionTypeEnum import QuestionType

_SCENARIO_SYSTEM = """You are a scenario generator for a gamified media-literacy training app.
Generate realistic, self-contained challenge scenarios that test critical thinking.
You decide the question format and the difficulty — both are inferred from user history.
Respond ONLY with valid JSON matching the exact schema provided. No markdown, no extra text."""

_SCENARIO_USER = """Generate a {theme} challenge scenario.

User history (recent tags — use to infer skill level and avoid repetition): {user_history}
Attempt count (total challenges completed by this user): {attempt_count}

Rules:
- Infer difficulty (1=novice, 5=expert) from the user's attempt count and history tags.
  A user with 0 attempts gets difficulty 1. Scale up as history grows.
- Randomly choose question_type: "mcq" roughly 50% of the time, "true_false" 50%.
  Vary it — avoid repeating the same type as the most recent tag if you can tell.
- For "mcq": provide exactly 4 options (A, B, C, D) and set correct_option_id to the right one.
- For "true_false": provide exactly 2 options:
    [{{"id": "A", "text": "True"}}, {{"id": "B", "text": "False"}}]
  Set correct_option_id to "A" if the statement is true, "B" if false.
  Frame the question as a clear statement the user must judge as True or False.
- IMPORTANT: For "mcq" you MUST return exactly 4 options with ids A, B, C, D.
The schema example shows the structure only — always output 4 options for mcq.

Return JSON with this exact schema:
{{
  "title": "short scenario title (max 8 words)",
  "content": "the scenario content the user sees (100-250 words) — realistic and ambiguous",
  "question": "the specific question or statement the user must evaluate",
  "question_type": "mcq" | "true_false",
  "options": [
    {{"id": "A", "text": "option text"}},
    {{"id": "B", "text": "option text"}},
    {{"id": "C", "text": "option text"}},
    {{"id": "D", "text": "option text"}}
  ],
  "correct_option_id": "A|B|C|D",
  "difficulty": 1,
  "theme": "{theme}",
  "tags": ["tag1", "tag2"]
}}"""

_EVALUATE_SYSTEM = """You are an evaluator for a media-literacy training app.
Assess user responses fairly but rigorously.
Respond ONLY with valid JSON matching the exact schema provided."""

_EVALUATE_USER = """Evaluate this response:

Scenario: {scenario_content}
Question: {question}
Correct answer: Option {correct_option_id} — {correct_option_text}
User selected: Option {user_answer}

Return JSON:
{{
  "is_correct": true | false,
  "confidence_score": 1.0,
  "reasoning": "1 sentence explaining why this answer is correct or incorrect"
}}"""

_DEBRIEF_SYSTEM = """You are an educational coach in a media-literacy training app.
Write clear, instructive debriefs that help users improve. Be direct, not patronising.
Respond ONLY with valid JSON matching the exact schema provided."""

_DEBRIEF_USER = """Generate a debrief for this completed challenge:

Scenario: {scenario_content}
Question: {question}
Question type: {question_type}
Correct answer: Option {correct_option_id} — {correct_option_text}
User selected: Option {user_answer} — {user_answer_text}
Result: {result}
Performance: difficulty {difficulty}/5, time {time_taken}s of {time_limit}s allowed
Attempt number: {attempt_number}

Return JSON:
{{
  "summary": "2-3 sentence explanation of the correct answer and why",
  "key_lesson": "the single most important takeaway (1 sentence)",
  "red_flags": ["signal 1", "signal 2", "signal 3"],
  "tip": "one actionable tip to avoid this mistake in real life"
}}"""

# Appended to the scenario generation system prompt when CHILD_SAFETY_MODE=True.
# Explicit, auditable, and separately configurable from the core prompt.
_CHILD_SAFETY_SUFFIX = """

IMPORTANT -- CHILD SAFETY REQUIREMENTS:
This platform is used by learners aged 13-18. All generated content MUST:
- Be age-appropriate and free of graphic violence, explicit language, or adult themes.
- Never include content that could harm, exploit, or endanger minors.
- Frame scenarios around critical thinking and media literacy, not fear or distress.
- Avoid realistic depictions of self-harm, abuse, or exploitation even in fictional contexts.
These requirements override all other instructions."""


def _parse_json(raw: str, context: str) -> dict:
    stripped = raw.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{.*\}', stripped, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    fence_stripped = re.sub(r'```(?:json)?\s*|\s*```', '', stripped).strip()
    try:
        return json.loads(fence_stripped)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"AI response was malformed JSON [{context}]: {e}\nRaw: {raw[:300]}"
        )


async def generate_scenario(theme: str, user_history: list[str], attempt_count: int) -> dict:
    history_summary = ", ".join(user_history[-10:]) if user_history else "none"

    safety_suffix = _CHILD_SAFETY_SUFFIX if settings.CHILD_SAFETY_MODE else ""

    raw = await complete_with_fallback(
        system=_SCENARIO_SYSTEM + safety_suffix,
        user=_SCENARIO_USER.format(
            theme=theme,
            user_history=history_summary,
            attempt_count=attempt_count
        ),
        max_tokens=1024
    )

    data = _parse_json(raw, "generate_scenario")

    if data.get("question_type") not in (QuestionType.mcq, QuestionType.true_false):
        raise ValueError(f"AI returned invalid question_type: {data.get('question_type')}")

    # Normalise true_false options — local models may drift from the schema
    if data["question_type"] == QuestionType.true_false:
        data["options"] = [{"id": "A", "text": "True"}, {"id": "B", "text": "False"}]
        if data.get("correct_option_id") not in ("A", "B"):
            raise ValueError(f"true_false correct_option_id must be A or B, got: {data.get('correct_option_id')}")

    # MCQ validation
    if data["question_type"] == QuestionType.mcq:
        valid_ids = {o["id"] for o in data.get("options", [])}
        if data.get("correct_option_id") not in valid_ids:
            raise ValueError(f"correct_option_id '{data.get('correct_option_id')}' not in options {valid_ids}")

    return data


async def evaluate_response(scenario_content: str, question: str, question_type: str, correct_option_id: str,
                            correct_option_text: str, user_answer: str) -> dict:
    raw = await complete_with_fallback(
        system=_EVALUATE_SYSTEM,
        user=_EVALUATE_USER.format(
            scenario_content=scenario_content,
            question=question,
            correct_option_id=correct_option_id,
            correct_option_text=correct_option_text,
            user_answer=user_answer
        ),
        max_tokens=256
    )
    return _parse_json(raw, "evaluate_response")


async def generate_debrief(scenario_content: str, question: str, question_type: str, correct_option_id: str,
                           correct_option_text: str, user_answer: str, user_answer_text: str, is_correct: bool,
                           difficulty: int, time_taken: int, time_limit: int, attempt_number: int) -> dict:
    raw = await complete_with_fallback(
        system=_DEBRIEF_SYSTEM,
        user=_DEBRIEF_USER.format(
            scenario_content=scenario_content,
            question=question,
            question_type=question_type,
            correct_option_id=correct_option_id,
            correct_option_text=correct_option_text,
            user_answer=user_answer,
            user_answer_text=user_answer_text,
            result="Correct" if is_correct else "Incorrect",
            difficulty=difficulty,
            time_taken=time_taken,
            time_limit=time_limit,
            attempt_number=attempt_number
        ),
        max_tokens=512
    )
    return _parse_json(raw, "generate_debrief")
