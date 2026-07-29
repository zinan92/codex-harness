"""Small label helpers used by the isolated router fixture."""


def prefix(label: str) -> str:
    """Return a stable visible prefix for ``label``."""
    return "label: {}".format(label)


def bracket(label: str) -> str:
    """Return ``label`` enclosed in square brackets."""
    return "[{}]".format(label)
