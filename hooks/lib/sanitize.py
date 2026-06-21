"""markdown 切片导出前的 PII 脱敏（references/markdown-切片导出.md §sanitize 落地）

第 1 版规则（首批数据出来后会迭代——见 references 未决问题 #1）：
- email → <email>
- home 路径用户名 → <home>/...
- API key 前缀模式（sk-* / ghp_* / AKIA* / Bearer *）→ <redacted>
- 私网 IP（10.* / 172.16-31.* / 192.168.*）→ <private-ip>
- 内部 URL（localhost / 127.0.0.1 / *.internal / *.local）→ <internal-url>
- 公网 URL（github / npm / *.com 等）→ 保留

返回 (sanitized_text, found_leaks) 让调用方可以验证「无漏脱」。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# email 匹配（基本足够，不追求 RFC 5322 完美）
RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")

# home 目录路径（POSIX：/home/<user>/... 或 macOS：/Users/<user>/...；含用户名 = PII）
RE_HOME_PATH = re.compile(r"(/(?:home|Users)/)[^/\s]+(/[^\s'\"`)\]]*)?")

# API key / token / secret 前缀
RE_API_KEY = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{20,}"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|AKIA[A-Z0-9]{16}"
    r"|AIza[A-Za-z0-9_-]{20,}"
    r"|xox[bpoasr]-[A-Za-z0-9-]{10,})\b"
)

# Bearer token（独立处理因为格式更松）
RE_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b", re.IGNORECASE)

# 私网 IP（10.0.0.0/8、172.16-31.0.0/12、192.168.0.0/16）
RE_PRIVATE_IP = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3})\b"
)

# 内部 URL（localhost / 127.x / *.internal / *.local / *.lan）
RE_INTERNAL_URL = re.compile(
    r"\bhttps?://"
    r"(?:localhost|127\.0\.0\.1|\d{1,3}(?:\.\d{1,3}){3}"
    r"|[\w-]+\.(?:internal|local|lan|corp|test|example))"
    r"(?::\d+)?(?:/[^\s'\"`)\]]*)?",
    re.IGNORECASE,
)


@dataclass
class SanitizeResult:
    """sanitize 后的文本 + 命中统计。

    counts 用于 sanity check：导出后 verify_no_leaks() 再扫一遍输出，
    确保没漏脱。
    """
    text: str
    counts: dict[str, int] = field(default_factory=dict)


def sanitize_text(text: str) -> SanitizeResult:
    """对单段文本做脱敏，返回 (新文本, 各类型命中次数)。"""
    counts: dict[str, int] = {}

    def _sub(pattern: re.Pattern[str], replacement: str, key: str, body: str) -> str:
        hits = [0]
        def replace(_m: re.Match[str]) -> str:
            hits[0] += 1
            return replacement
        new_body = pattern.sub(replace, body)
        if hits[0]:
            counts[key] = hits[0]
        return new_body

    # 顺序敏感：先 home_path 再 internal_url（path 可能含 url 片段）
    text = _sub(RE_EMAIL, "<email>", "email", text)
    # API key 优先于通用 home_path，否则 sk-xxx 出现在 home_path 里可能被先吞
    text = _sub(RE_API_KEY, "<redacted>", "api_key", text)
    text = _sub(RE_BEARER, "Bearer <redacted>", "bearer", text)
    text = _sub(RE_INTERNAL_URL, "<internal-url>", "internal_url", text)
    text = _sub(RE_PRIVATE_IP, "<private-ip>", "private_ip", text)

    # home path 最后处理（脱掉用户名段，保留 /home/ 或 /Users/ + 后续路径）
    def home_replace(m: re.Match[str]) -> str:
        counts["home_path"] = counts.get("home_path", 0) + 1
        prefix = m.group(1)  # /home/ or /Users/
        rest = m.group(2) or ""
        # /home/<user>/foo → <home>/foo
        return f"<home>{rest}" if rest else "<home>"
    text = RE_HOME_PATH.sub(home_replace, text)

    return SanitizeResult(text=text, counts=counts)


def verify_no_leaks(text: str) -> list[tuple[str, str]]:
    """扫描已 sanitize 文本，确认无漏脱。返回 [(rule_name, leaked_snippet), ...]。

    用于导出后做 sanity check（输出空列表 = 没漏脱）。
    """
    leaks: list[tuple[str, str]] = []
    for name, pat in [
        ("email", RE_EMAIL),
        ("api_key", RE_API_KEY),
        ("bearer", RE_BEARER),
        ("internal_url", RE_INTERNAL_URL),
        ("private_ip", RE_PRIVATE_IP),
        ("home_path", RE_HOME_PATH),
    ]:
        for m in pat.finditer(text):
            leaks.append((name, m.group(0)))
    return leaks


def main() -> int:
    """CLI：从 stdin 读文本，脱敏后输出到 stdout，统计到 stderr。"""
    import sys
    text = sys.stdin.read()
    result = sanitize_text(text)
    sys.stdout.write(result.text)
    if result.counts:
        sys.stderr.write("[sanitize] hits: ")
        sys.stderr.write(", ".join(f"{k}={v}" for k, v in sorted(result.counts.items())))
        sys.stderr.write("\n")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
