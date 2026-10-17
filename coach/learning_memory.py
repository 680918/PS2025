"""Explicit user-owned learning notes, never inferred from model or source text."""

import re
import unicodedata


MAX_MEMORIES = 20
MAX_MEMORY_LENGTH = 300


class MemoryInputError(ValueError):
    pass


def memory_request(text):
    """Only a direct, leading request authorizes persistence; return None otherwise."""
    match = re.fullmatch(
        r"(?:请(?:你)?(?:帮我)?记住|帮我记住)[：:，,\s]*(.*)", text, re.DOTALL
    )
    return match.group(1).strip() if match else None


def validate_memory(content):
    if not isinstance(content, str):
        raise MemoryInputError("请写下想保留的一条学习目标、基础或讲解偏好。")
    content = content.strip()
    if not 1 <= len(content) <= MAX_MEMORY_LENGTH:
        raise MemoryInputError(
            "每条学习记忆需要 1–300 个字符，请一次保留一条简明的信息。"
        )
    if any(
        unicodedata.category(char) == "Cs"
        or (unicodedata.category(char) == "Cc" and char not in "\n\t")
        for char in content
    ):
        raise MemoryInputError("记忆中含有无法保存的控制字符，请重新填写。")
    # Common credential assignments are not useful learning preferences. Do not
    # claim this catches every secret, or that it removes anything from chat logs.
    if re.search(
        r"(?:密码|口令|授权码|验证码|密钥|api[ _-]?key|access[ _-]?token|password|secret)\s*(?:是|为|[:=：])\s*\S+|-----BEGIN .*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{16,}",
        content,
        re.I,
    ):
        raise MemoryInputError(
            "请只保存学习信息，不要把密码、验证码或密钥放入长期记忆。"
        )
    return content
