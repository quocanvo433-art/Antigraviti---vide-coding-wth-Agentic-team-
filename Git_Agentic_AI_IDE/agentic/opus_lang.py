"""
DNA Header v16.7 - Sovereign Purity
Role: OPUS_LANG (Ngôn ngữ nén tối ưu token)
Layer: 5 (Foundation Protocol)

OpusLang — Ngôn ngữ nén riêng của Opus Collective Intelligence.
Mọi engram, handover, log đều được mã hóa bằng ngôn ngữ này.
Mục tiêu: Nén ~80% token so với ngôn ngữ tự nhiên, vẫn đọc được bằng mắt.

CÚ PHÁP:
    <from_role>→<to_role> | <action>(<target>):<result> | P:<pending>

BẢN ĐỒ KÝ HIỆU (CORE SYMBOLS — cố định, không thay đổi):
    Roles:  A=Architect  C=Coder  D=auDitor  S=Strategist  L=Leader
    Flow:   → = chuyển   | = ngăn   : = kết quả   ; = multi-result
    Status: ✓=pass  ✗=fail  ~=partial  ?=unknown  !=critical
    Prefix: P:=pending  R:=requires  B:=blocked  X:=cancelled
    Action: fix() edit() add() del() test() audit() plan() review()
            read() create() deploy() verify() merge() rollback()
    Domain: syn=syntax  dna=DNA  ast=AST  cfg=config  dep=dependency
            mem=memory  net=network  sec=security  perf=performance
    Quant:  3/5 = 3 trong 5  >< = so sánh  += thêm  -= bớt

VÍ DỤ:
    A→C | fix(a04.brain):syn✓dna✓ | P:boost_prompt
    C→D | test(genesis):PASS(3/3) | P:none
    L   | plan(opus_v2):5_layers | R:approval
    D→C | audit(agentic/*):syn✓dna✗(2) | P:fix_headers
"""

import re
from datetime import datetime


# ── Core Symbol Tables ────────────────────────────────────────────
ROLE_MAP = {
    # Aliases first (will be overwritten in ROLE_DECODE by primary names)
    "Analyst": "A", "Builder": "C", "Quality": "D", "Security": "S",
    # Primary names last (these win in ROLE_DECODE)
    "Architect": "A", "Coder": "C", "Auditor": "D",
    "Strategist": "S", "Leader": "L",
}
ROLE_DECODE = {v: k for k, v in ROLE_MAP.items()}

ACTION_MAP = {
    "fixed": "fix", "edited": "edit", "added": "add", "deleted": "del",
    "tested": "test", "audited": "audit", "planned": "plan",
    "reviewed": "review", "created": "create", "deployed": "deploy",
    "verified": "verify", "merged": "merge", "rolled back": "rollback",
    "read": "read", "implemented": "impl", "upgraded": "upg",
    "integrated": "intg", "configured": "cfg", "analyzed": "anlz",
}

STATUS_MAP = {
    "passed": "✓", "pass": "✓", "ok": "✓", "success": "✓", "done": "✓",
    "failed": "✗", "fail": "✗", "error": "✗", "broken": "✗",
    "partial": "~", "in progress": "~", "wip": "~",
    "unknown": "?", "pending": "?",
    "critical": "!", "urgent": "!", "blocker": "!",
}

DOMAIN_MAP = {
    "syntax": "syn", "dna": "dna", "ast": "ast", "config": "cfg",
    "dependency": "dep", "memory": "mem", "network": "net",
    "security": "sec", "performance": "perf", "database": "db",
    "redis": "rds", "docker": "dkr", "purity": "pur",
}


# ── Encoder ───────────────────────────────────────────────────────
def encode_role(role_name: str) -> str:
    """Encode role name to single letter."""
    return ROLE_MAP.get(role_name, role_name[0].upper())


def encode_transition(from_role: str, to_role: str = None) -> str:
    """Encode role transition."""
    fr = encode_role(from_role)
    if to_role:
        return f"{fr}→{encode_role(to_role)}"
    return fr


def encode_action(verb: str, target: str, results: dict = None) -> str:
    """Encode an action with its results.

    Args:
        verb: Natural language verb (e.g., "fixed", "tested")
        target: File or component name
        results: Dict of {check_name: status_str}

    Returns:
        Encoded string like "fix(a04.brain):syn✓dna✓"
    """
    action = ACTION_MAP.get(verb.lower(), verb[:4].lower())

    # Compress target: strip paths, keep basename, shorten
    target_short = target.replace(".py", "").split("/")[-1]

    if results:
        encoded_results = []
        for check, status in results.items():
            domain = DOMAIN_MAP.get(check.lower(), check[:3].lower())
            sym = STATUS_MAP.get(status.lower(), status)
            encoded_results.append(f"{domain}{sym}")
        return f"{action}({target_short}):{';'.join(encoded_results)}"
    return f"{action}({target_short})"


def encode_pending(items: list) -> str:
    """Encode pending items."""
    if not items:
        return "P:none"
    compressed = [i.replace(" ", "_").lower()[:20] for i in items]
    return f"P:{','.join(compressed)}"


def encode_log_entry(
    from_role: str,
    to_role: str = None,
    action_verb: str = "",
    target: str = "",
    results: dict = None,
    pending: list = None,
    timestamp: bool = False,
) -> str:
    """Encode a complete log entry in OpusLang.

    Example output: "A→C | fix(a04.brain):syn✓dna✓ | P:boost_prompt"
    """
    parts = []

    # Timestamp prefix (optional, compact)
    if timestamp:
        ts = datetime.now().strftime("%H%M")
        parts.append(f"T{ts}")

    # Role transition
    parts.append(encode_transition(from_role, to_role))

    # Action
    if action_verb and target:
        parts.append(encode_action(action_verb, target, results))

    # Pending
    if pending is not None:
        parts.append(encode_pending(pending))

    return " | ".join(parts)


def encode_session_summary(entries: list) -> str:
    """Encode an entire session as multi-line OpusLang.

    Args:
        entries: List of dicts, each with keys matching encode_log_entry params.

    Returns:
        Multi-line OpusLang string.
    """
    lines = []
    for entry in entries:
        lines.append(encode_log_entry(**entry))
    return "\n".join(lines)


# ── Decoder ───────────────────────────────────────────────────────
def decode_role(code: str) -> str:
    """Decode single letter to role name."""
    return ROLE_DECODE.get(code, f"Role({code})")


def decode_entry(opus_line: str) -> dict:
    """Decode a single OpusLang line into structured dict.

    Input:  "A→C | fix(a04.brain):syn✓dna✓ | P:boost_prompt"
    Output: {
        "from_role": "Architect", "to_role": "Coder",
        "action": "fix", "target": "a04.brain",
        "results": {"syn": "✓", "dna": "✓"},
        "pending": ["boost_prompt"]
    }
    """
    result = {"from_role": None, "to_role": None, "action": None,
              "target": None, "results": {}, "pending": []}

    parts = [p.strip() for p in opus_line.split("|")]

    for part in parts:
        # Timestamp
        if part.startswith("T") and len(part) == 5 and part[1:].isdigit():
            result["timestamp"] = part[1:]
            continue

        # Role transition: "A→C" or just "A"
        if "→" in part and len(part) <= 5:
            roles = part.split("→")
            result["from_role"] = decode_role(roles[0])
            result["to_role"] = decode_role(roles[1])
            continue
        elif len(part) == 1 and part.isupper():
            result["from_role"] = decode_role(part)
            continue

        # Pending: "P:boost_prompt,other"
        if part.startswith("P:"):
            pending_str = part[2:]
            if pending_str != "none":
                result["pending"] = pending_str.split(",")
            continue

        # Action: "fix(a04.brain):syn✓dna✓"
        action_match = re.match(r"(\w+)\(([^)]+)\)(?::(.+))?", part)
        if action_match:
            result["action"] = action_match.group(1)
            result["target"] = action_match.group(2)
            if action_match.group(3):
                # Parse results like "syn✓dna✓" or "syn✓;dna✗"
                res_str = action_match.group(3)
                for res_part in res_str.split(";"):
                    # Match patterns like "syn✓" or "PASS(3/3)"
                    res_match = re.match(r"([a-zA-Z]+)([✓✗~?!]|\w+\([^)]*\))", res_part)
                    if res_match:
                        result["results"][res_match.group(1)] = res_match.group(2)
                    else:
                        result["results"]["_raw"] = res_part
            continue

    return result


def decode_session(opus_text: str) -> list:
    """Decode multi-line OpusLang into list of structured dicts."""
    entries = []
    for line in opus_text.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            entries.append(decode_entry(line))
    return entries


# ── Metrics ───────────────────────────────────────────────────────
def compression_ratio(original_text: str, encoded_text: str) -> float:
    """Calculate compression ratio. >1.0 means compression happened."""
    if not encoded_text:
        return 0.0
    return len(original_text) / len(encoded_text)


def estimate_token_savings(original_text: str, encoded_text: str) -> dict:
    """Estimate token savings (rough: 1 token ≈ 4 chars for English)."""
    orig_tokens = len(original_text) / 4
    enc_tokens = len(encoded_text) / 4
    return {
        "original_chars": len(original_text),
        "encoded_chars": len(encoded_text),
        "original_tokens_est": round(orig_tokens),
        "encoded_tokens_est": round(enc_tokens),
        "savings_pct": round((1 - enc_tokens / max(orig_tokens, 1)) * 100, 1),
        "ratio": round(compression_ratio(original_text, encoded_text), 2),
    }


# ── CLI ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import json as _json

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 opus_lang.py encode '<from_role>' '<to_role>' '<verb>' '<target>' '<results_json>'")
        print("  python3 opus_lang.py decode '<opus_line>'")
        print("  python3 opus_lang.py demo")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "demo":
        # Demonstrate encoding + decoding + compression
        print("═══ OpusLang Demo ═══\n")

        natural = (
            "Chuyển từ Architect sang Coder, đã sửa file a04_brain.py, "
            "kiểm tra syntax thành công, DNA Header đúng chuẩn, "
            "việc còn lại là cập nhật boost prompt"
        )
        encoded = encode_log_entry(
            from_role="Architect", to_role="Coder",
            action_verb="fixed", target="agents/logic/a04_brain.py",
            results={"syntax": "pass", "dna": "pass"},
            pending=["boost_prompt"],
        )
        print(f"Natural:  {natural}")
        print(f"Encoded:  {encoded}")
        print(f"Decoded:  {_json.dumps(decode_entry(encoded), ensure_ascii=False, indent=2)}")

        stats = estimate_token_savings(natural, encoded)
        print(f"\nCompression: {stats['savings_pct']}% token savings")
        print(f"Ratio: {stats['ratio']}x ({stats['original_chars']} → {stats['encoded_chars']} chars)")

        # Multi-entry session
        print("\n═══ Session Summary ═══\n")
        session = [
            {"from_role": "Leader", "action_verb": "planned", "target": "opus_v2",
             "results": {"scope": "pass"}, "pending": ["approval"]},
            {"from_role": "Architect", "to_role": "Coder",
             "action_verb": "created", "target": "opus_lang.py",
             "results": {"syntax": "pass", "ast": "pass"}, "pending": ["test"]},
            {"from_role": "Coder", "to_role": "Auditor",
             "action_verb": "tested", "target": "opus_lang.py",
             "results": {"syntax": "pass", "dna": "pass"}, "pending": []},
        ]
        summary = encode_session_summary(session)
        print(summary)

    elif cmd == "encode" and len(sys.argv) >= 5:
        fr = sys.argv[2]
        to = sys.argv[3] if sys.argv[3] != "_" else None
        verb = sys.argv[4] if len(sys.argv) > 4 else ""
        target = sys.argv[5] if len(sys.argv) > 5 else ""
        results = _json.loads(sys.argv[6]) if len(sys.argv) > 6 else None
        print(encode_log_entry(fr, to, verb, target, results))

    elif cmd == "decode" and len(sys.argv) >= 3:
        line = " ".join(sys.argv[2:])
        print(_json.dumps(decode_entry(line), ensure_ascii=False, indent=2))
