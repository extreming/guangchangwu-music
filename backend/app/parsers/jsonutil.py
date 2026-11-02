"""Small helpers for JSON buried in share pages. Not platform-specific."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any
from urllib.parse import unquote


def walk(node: Any) -> Iterator[Any]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def extract_balanced_json(text: str, start: int) -> str | None:
    if start < 0 or start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_str = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_str:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_str = False
            continue
        if char == '"':
            in_str = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def parse_embedded_json(html: str, markers: tuple[str, ...]) -> Any | None:
    for marker in markers:
        cursor = 0
        while True:
            idx = html.find(marker, cursor)
            if idx < 0:
                break
            start = html.find("{", idx + len(marker))
            cursor = idx + len(marker)
            if start < 0:
                continue
            blob = extract_balanced_json(html, start)
            if not blob:
                continue
            try:
                return json.loads(blob)
            except json.JSONDecodeError:
                continue
    return None


def parse_script_json(html: str, script_id: str) -> Any | None:
    pattern = re.compile(
        rf'<script[^>]*\bid=["\']{re.escape(script_id)}["\'][^>]*>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(html)
    if not match:
        return None
    raw = match.group(1).strip()
    candidates = [raw]
    decoded = unquote(raw)
    if decoded != raw:
        candidates.append(decoded)
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, (dict, list)):
            return data
    return None


def json_unescape(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw.replace("\\/", "/").replace("\\u0026", "&")
