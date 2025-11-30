"""Question extraction from agent tmux output."""

import re


def _extract_from_askuserquestion(text: str) -> str | None:
    """
    Extract question from AskUserQuestion tool invocation.

    Looks for pattern:
    <parameter name="questions">[{"question": "...", ...}]</parameter>

    Args:
        text: Text to search

    Returns:
        First question found, or None
    """
    pattern = r'<parameter name="questions">\s*\[\s*\{\s*"question":\s*"([^"]+)"'
    match = re.search(pattern, text)
    return match.group(1) if match else None


def _extract_from_question_marks(text: str) -> str | None:
    """
    Extract most recent question ending with '?', including multi-line questions.

    Searches from bottom to top to get the most recent question.
    When a line ending with '?' is found, looks backward to capture
    preceding lines that are part of the same multi-line question.

    Args:
        text: Text to search

    Returns:
        Most recent question (single or multi-line), or None
    """
    lines = text.split('\n')

    # Find the line ending with '?'
    question_end_idx = None
    for idx in range(len(lines) - 1, -1, -1):
        if lines[idx].strip().endswith('?'):
            question_end_idx = idx
            break

    if question_end_idx is None:
        return None

    # Collect the question line and any preceding lines that are part of it
    question_lines = [lines[question_end_idx].strip()]

    # Look backward for additional lines that are part of the question
    for idx in range(question_end_idx - 1, -1, -1):
        line = lines[idx].strip()

        # Stop at blank lines (question boundary)
        if not line:
            break

        # Stop at option markers (not part of question)
        if line.startswith('❯') or line.startswith(tuple('0123456789')):
            break

        # This line is part of the question
        question_lines.insert(0, line)

    # Join lines with space and return
    return ' '.join(question_lines)


def extract_question_from_text(text: str) -> str | None:
    """
    Extract pending question from agent output.

    Handles multiple question patterns (in priority order):
    1. AskUserQuestion tool invocations (highest priority)
    2. Lines ending with '?' (fallback)

    Args:
        text: Agent output text to parse

    Returns:
        Extracted question text, or None if no question found

    Examples:
        >>> extract_question_from_text("Should I proceed?")
        'Should I proceed?'

        >>> extract_question_from_text("No questions here")
        None
    """
    if not text:
        return None

    # Try AskUserQuestion pattern first (more structured)
    question = _extract_from_askuserquestion(text)
    if question:
        return question

    # Fall back to question mark pattern
    return _extract_from_question_marks(text)
