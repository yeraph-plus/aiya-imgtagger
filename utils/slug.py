import re

_INVALID = re.compile(r"[^a-z0-9_-]+")
_MULTI_UNDERSCORE = re.compile(r"_+")
_LEADING_TRAILING = re.compile(r"^_+|_+$")


def sanitize_slug(value: str) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower().replace(" ", "_")
    s = _INVALID.sub("_", s)
    s = _MULTI_UNDERSCORE.sub("_", s)
    s = _LEADING_TRAILING.sub("", s)
    return s


def sanitize_preset_name(value: str) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    s = re.sub(r"\.{2,}", "_", s)
    s = re.sub(r"[\\/]+", "_", s)
    s = _LEADING_TRAILING.sub("_", s)
    s = _LEADING_TRAILING.sub("", s)
    return s