"""Prompt templates (markdown files in this folder) and helpers for filling them in."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_PROMPT_DIR = Path(__file__).parent
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


@lru_cache
def load_prompt(name: str) -> str:
    """Read `<name>.md` from the prompts folder."""
    path = _PROMPT_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def render_prompt(template_name: str, /, **values: str) -> str:
    """Fill `{{placeholder}}` slots in a template.

    Raises if a placeholder has no value or a value has no placeholder, so a typo can never
    silently ship a broken prompt. Substitution is a single pass: inserted values are never
    re-scanned for placeholders.
    """
    template = load_prompt(template_name)
    placeholders = set(_PLACEHOLDER_RE.findall(template))
    missing = placeholders - values.keys()
    unused = values.keys() - placeholders
    if missing:
        raise ValueError(f"Prompt '{template_name}' is missing values for: {sorted(missing)}")
    if unused:
        raise ValueError(f"Prompt '{template_name}' has unused values: {sorted(unused)}")
    return _PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], template)


def wrap_untrusted(tag: str, text: str) -> str:
    """Wrap untrusted text in <tag>...</tag>, removing any copies of the tag inside it.

    Without the removal, a document could contain its own closing tag and "escape" the
    data block.
    """
    cleaned = re.sub(rf"</?{re.escape(tag)}\s*>", "", text, flags=re.IGNORECASE)
    return f"<{tag}>\n{cleaned.strip()}\n</{tag}>"