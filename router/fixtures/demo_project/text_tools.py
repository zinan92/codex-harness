"""Small text helpers used by the isolated router fixture."""


def normalize(text: str) -> str:
    """Trim surrounding whitespace."""
    return text.strip()


def shout(text: str) -> str:
    """Return normalized text in uppercase with exactly one trailing exclamation."""
    normalized = normalize(text).upper()
    return normalized.rstrip("!") + "!"
