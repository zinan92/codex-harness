"""Small text helpers used by the isolated router fixture."""


def normalize(text: str) -> str:
    """Trim surrounding whitespace."""
    return text.strip()
