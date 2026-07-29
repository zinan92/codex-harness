"""Small number helpers used by the isolated router fixture."""


def is_even(value: int) -> bool:
    """Report whether ``value`` is even."""
    return value % 2 == 0
