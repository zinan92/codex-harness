"""Small label helpers used by the isolated router fixture."""


def prefix(label: str) -> str:
    """Return a stable visible prefix for ``label``."""
    return "label: {}".format(label)
