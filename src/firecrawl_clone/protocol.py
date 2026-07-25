"""JSON protocol types and serialization."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from typing import Any

from .errors import FirecrawlError


# ── Request types ──────────────────────────────────────────────

@dataclass
class Command:
    cmd: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, raw: str) -> Command:
        """Parse a JSON command line from stdin."""
        data = json.loads(raw.strip())
        cmd = data.pop("cmd")
        return cls(cmd=cmd, params=data)


# ── Response types ─────────────────────────────────────────────

@dataclass
class Link:
    url: str
    text: str


@dataclass
class SuccessResponse:
    ok: bool = True
    markdown: str = ""
    images: dict[str, str] = field(default_factory=dict)  # uuid -> local path
    links: list[Link] = field(default_factory=list)
    path: str = ""          # for screenshot / save_image
    error: str = ""
    message: str = ""       # generic status message

    def to_json(self) -> str:
        return json.dumps({
            "ok": self.ok,
            "markdown": self.markdown,
            "images": self.images,
            "links": [asdict(l) for l in self.links],
            **({"path": self.path} if self.path else {}),
            **({"message": self.message} if self.message else {}),
        })


@dataclass
class ErrorResponse:
    ok: bool = False
    error: str = ""
    code: str = ""

    @classmethod
    def from_exception(cls, exc: FirecrawlError) -> ErrorResponse:
        return cls(ok=False, error=str(exc), code=exc.code)

    @classmethod
    def from_message(cls, message: str, code: str = "command_error") -> ErrorResponse:
        return cls(ok=False, error=message, code=code)

    def to_json(self) -> str:
        return json.dumps({
            "ok": self.ok,
            "error": self.error,
            "code": self.code,
        })


Response = SuccessResponse | ErrorResponse
