"""PII 脱敏网关。

进模型之前把人名以外的强标识符（手机号、身份证、银行卡、邮箱）换成占位符，
模型输出后再按映射表回填，格式保持不变（format-preserving）。
这样"用云端大模型"和"不把员工个人信息送出去"可以同时成立，审计日志里只留占位符。

占位符用 GUID 风格短码，避免模型把它当成自然语言改写掉。
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("IDCARD", re.compile(r"\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b")),
    ("BANK", re.compile(r"\b\d{16,19}\b")),
    ("PHONE", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
]


@dataclass
class MaskResult:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)

    @property
    def masked_count(self) -> int:
        return len(self.mapping)


def mask(text: str) -> MaskResult:
    if not text:
        return MaskResult(text=text)
    mapping: dict[str, str] = {}
    out = text
    for label, pattern in _PATTERNS:
        def _repl(match: re.Match, label: str = label) -> str:
            token = f"<{label}_{uuid.uuid4().hex[:6].upper()}>"
            mapping[token] = match.group(0)
            return token

        out = pattern.sub(_repl, out)
    return MaskResult(text=out, mapping=mapping)


def unmask(text: str, mapping: dict[str, str]) -> str:
    if not text or not mapping:
        return text
    for token, original in mapping.items():
        text = text.replace(token, original)
    return text


def audit_preview(masked: MaskResult, limit: int = 120) -> dict:
    """只记录占位符和命中数量，不落原始敏感值。"""
    return {
        "masked_count": masked.masked_count,
        "kinds": sorted({t.split("_")[0].strip("<") for t in masked.mapping}),
        "preview": masked.text[:limit],
    }
