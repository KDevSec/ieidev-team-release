"""Tag naming convention for kdev-injected nodes/edges in UA graphs.

All kdev tags use the form `kdev:<kind>` (kind-only) or `kdev:<kind>:<value>`.
Values must match `[a-z0-9_.-]+`. Multiple values use multiple tags.
"""

from __future__ import annotations

import re

KDEV_PREFIX = "kdev:"

KIND_SECURITY_RULE = "security_rule"
KIND_VULNERABILITY = "vulnerability"
KIND_COMPLIANCE = "compliance"

_KIND_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_VALUE_RE = re.compile(r"^[a-z0-9_.\-]+$")


class InvalidTagError(ValueError):
    """Raised when a tag does not satisfy the kdev naming convention."""


def make_tag(kind: str, value: str | None = None) -> str:
    if not kind or not _KIND_RE.match(kind):
        raise InvalidTagError(
            f"kind must match {_KIND_RE.pattern!r}, got {kind!r}"
        )
    if value is None:
        return f"{KDEV_PREFIX}{kind}"
    if not _VALUE_RE.match(value):
        raise InvalidTagError(
            f"value must match {_VALUE_RE.pattern!r}, got {value!r}"
        )
    return f"{KDEV_PREFIX}{kind}:{value}"


def is_kdev_tag(tag: str) -> bool:
    if not tag.startswith(KDEV_PREFIX):
        return False
    rest = tag[len(KDEV_PREFIX):]
    return bool(rest) and _KIND_RE.match(rest.split(":", 1)[0]) is not None


def parse_tag(tag: str) -> tuple[str, str | None]:
    if not is_kdev_tag(tag):
        raise InvalidTagError(f"not a kdev tag: {tag!r}")
    rest = tag[len(KDEV_PREFIX):]
    if ":" in rest:
        kind, value = rest.split(":", 1)
        if not _VALUE_RE.match(value):
            raise InvalidTagError(
                f"value must match {_VALUE_RE.pattern!r}, got {value!r}"
            )
        return kind, value
    return rest, None


def has_kind(tags: list[str], kind: str) -> bool:
    for tag in tags:
        if not is_kdev_tag(tag):
            continue
        try:
            parsed_kind, _ = parse_tag(tag)
        except InvalidTagError:
            continue
        if parsed_kind == kind:
            return True
    return False


def extract_kind(tags: list[str]) -> str | None:
    """Return the first kind-only tag (kdev:<kind>) found."""
    for tag in tags:
        if not is_kdev_tag(tag):
            continue
        try:
            kind, value = parse_tag(tag)
        except InvalidTagError:
            continue
        if value is None:
            return kind
    return None


def extract_value(tags: list[str], kind: str) -> str | None:
    """Return the value of the first tag matching kdev:<kind>:<value>."""
    for tag in tags:
        if not is_kdev_tag(tag):
            continue
        try:
            parsed_kind, value = parse_tag(tag)
        except InvalidTagError:
            continue
        if parsed_kind == kind and value is not None:
            return value
    return None
