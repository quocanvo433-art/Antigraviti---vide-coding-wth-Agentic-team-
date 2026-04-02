"""
DNA Header v16.7 - Sovereign Purity
Role: OPUSLANG (Ngôn ngữ nén nội bộ Team Agentic AI)
Layer: 6 (Internal Agent Communication — Anh không cần đọc)

OpusLang v2.0 — Encode/Decode giữa agents.
Mục đích: Nén engram, handover, session summary xuống 15-25 tokens.
Portable: Chỉ cần .opus/codebook.json + file này.
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# CODEBOOK LOADER
# ══════════════════════════════════════════════════════════════════════════════

_CODEBOOK = None
_CODEBOOK_PATH = None


def _find_codebook() -> Path:
    """Tìm codebook.json — tự tìm gốc project bằng .opus/ directory."""
    # Thử từ vị trí hiện tại
    candidates = [
        Path(__file__).resolve().parent.parent / ".opus" / "codebook.json",
        Path.cwd() / ".opus" / "codebook.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError("Không tìm thấy .opus/codebook.json — OpusLang không thể khởi tạo.")


def load_codebook(force=False) -> dict:
    """Nạp codebook vào bộ nhớ. Gọi 1 lần đầu phiên."""
    global _CODEBOOK, _CODEBOOK_PATH
    if _CODEBOOK and not force:
        return _CODEBOOK
    
    path = _find_codebook()
    with open(path, 'r', encoding='utf-8') as f:
        _CODEBOOK = json.load(f)
    _CODEBOOK_PATH = path
    return _CODEBOOK


def get_file_alias(filepath: str) -> str:
    """Chuyển filepath → alias ngắn. VD: 'tools/A04_BRAIN_HELPER.py' → '@HELPER'"""
    cb = load_codebook()
    # Reverse lookup
    for alias, full_path in cb.get("file_aliases", {}).items():
        if filepath.endswith(full_path) or filepath == full_path:
            return alias
    # Fallback: dùng basename
    return "@" + Path(filepath).stem[:8].upper()


def resolve_alias(alias: str) -> str:
    """Giải mã alias → filepath đầy đủ. VD: '@HELPER' → 'tools/A04_BRAIN_HELPER.py'"""
    cb = load_codebook()
    return cb.get("file_aliases", {}).get(alias, alias)


# ══════════════════════════════════════════════════════════════════════════════
# ENCODER — Human Text → OpusLang
# ══════════════════════════════════════════════════════════════════════════════

def encode(text: str, category: str = "L") -> str:
    """
    Nén text tiếng Việt/Anh thành OpusLang token string.
    
    Args:
        text: Nội dung cần nén (VD: "Flash Brief #3: Nâng cấp Genesis VSA4...")
        category: Prefix category (L=lesson, S=session, E=error, P=pattern, etc.)
    
    Returns:
        OpusLang encoded string (VD: "L:F#3:@BRAIN→VSA4|§vsa+kin|✓")
    """
    cb = load_codebook()
    result = text
    
    # 1. Replace file paths → aliases
    for alias, full_path in cb.get("file_aliases", {}).items():
        result = result.replace(full_path, alias)
        # Also replace basename
        basename = Path(full_path).name
        result = result.replace(basename, alias)
    
    # 2. Replace domain terms → short codes
    for code, full_term in cb.get("domain_aliases", {}).items():
        result = re.sub(re.escape(full_term), code, result, flags=re.IGNORECASE)
    
    # 3. Replace role names → short codes
    for code, full_role in cb.get("role_aliases", {}).items():
        if full_role.split("(")[0].strip().lower() in result.lower():
            result = re.sub(re.escape(full_role.split("(")[0].strip()), code, result, flags=re.IGNORECASE)
    
    # 4. Replace status words → symbols (order matters: longer first)
    status_map = [
        ("HOÀN TẤT 100%", "✓"), ("HOÀN TẤT", "✓"), ("hoàn tất", "✓"),
        ("PASS", "✓"), ("FAIL", "✗"), ("PARTIAL", "⚠"),
        ("BLOCKED", "⛔"), ("IN PROGRESS", "IP"), ("DONE", "D"),
        ("GREEN", "G"), ("YELLOW", "Y"), ("RED", "R"),
        ("nâng cấp", "→"), ("thêm ", "+"), ("tích hợp", "⊕"),
        ("thay đổi", "Δ"), ("cập nhật", "Δ"), ("chỉnh sửa", "Δ"),
        ("đã sửa", "Δ"), ("đã thêm", "+"), ("đã hoàn tất", "✓"),
        ("đã tạo", "+"), ("đã xóa", "−"),
        # Long phrases → compress
        ("Audit: ", ""), ("Audit ", ""), ("audit ", ""),
        ("syntax OK", "syn✓"), ("dna OK", "dna✓"),
        ("syn✓ dna✓", "✓✓"),
        ("Flash Brief", "F#"), ("Flash brief", "F#"),
        ("Brief ", "B"), ("brief ", "B"),
        ("Prompt ", "P:"), ("prompt ", "P:"),
        ("Session ", "S:"), ("session ", "S:"),
        ("Kinematics", "KIN"), ("kinematics", "KIN"),
        ("Fingerprint", "FP"), ("fingerprint", "FP"),
        ("Composite Man", "CM"), ("composite man", "CM"),
        ("Wyckoff", "WK"), ("wyckoff", "WK"),
        ("Elliott", "EW"), ("elliott", "EW"),
        ("Boosting", "BOOST"), ("boosting", "BOOST"),
        ("Genesis", "GEN"), ("genesis", "GEN"),
        ("Realtime", "RT"), ("realtime", "RT"),
        ("vector", "vec"), ("Vector", "vec"),
        ("function", "fn"), ("hàm", "fn"),
        ("tổng cộng", "Σ"), ("tổng", "Σ"),
        ("file ", "f:"), ("File ", "f:"),
        ("dòng ", "L"), ("line ", "L"),
    ]
    for word, sym in status_map:
        result = result.replace(word, sym)
    
    # 5. Strip filler words (Vietnamese + English) — aggressive
    fillers = [
        # Vietnamese fillers
        "đã ", "được ", "các ", "của ", "cho ", "với ", "và ", "trong ", "để ",
        "vào ", "sau ", "khi ", "từ ", "bằng ", "có ", "là ", "này ", "đang ",
        "những ", "một ", "một số ", "cần ", "nên ", "sẽ ", "phải ",
        "tại ", "trên ", "dưới ", "giữa ", "về ", "theo ", "qua ",
        "rồi ", "xong ", "còn ", "lại ", "thì ", "mà ", "cũng ",
        "trả về ", "bao gồm ", "cụ thể ",
        # English fillers  
        "the ", "a ", "an ", "is ", "are ", "was ", "were ",
        "has ", "have ", "had ", "been ", "being ",
        "that ", "which ", "with ", "from ", "into ",
        # Metadata prefixes
        "LESSON: ", "SESSION: ", "ERROR: ", "OPUS_SESSION_",
        "CHECKPOINT: ", "HANDOVER: ",
    ]
    for filler in fillers:
        result = result.replace(filler, "")
    
    # 6. Strip redundant punctuation
    result = result.replace(". ", "|").replace(".", "|")  # periods → pipes
    result = result.replace(", ", ",").replace("; ", ";")
    result = result.replace("  ", " ").replace("||", "|")
    result = result.replace("(", "").replace(")", "")
    
    # 7. Collapse whitespace
    result = re.sub(r'\s+', ' ', result).strip()
    result = re.sub(r'\|+', '|', result)  # collapse multiple pipes
    result = result.strip('|')  # strip leading/trailing pipes
    
    # 8. Add category prefix
    if not result.startswith(f"{category}:"):
        result = f"{category}:{result}"
    
    return result


# ══════════════════════════════════════════════════════════════════════════════
# DECODER — OpusLang → Human Text
# ══════════════════════════════════════════════════════════════════════════════

def decode(encoded: str) -> str:
    """
    Giải mã OpusLang → text đọc được (cho agent hiểu, KHÔNG cho Anh).
    
    Args:
        encoded: OpusLang string (VD: "L:F#3:@BRAIN→VSA4|§vsa+kin|✓")
    
    Returns:
        Human-readable text cho agent
    """
    cb = load_codebook()
    result = encoded
    
    # 1. Decode file aliases
    for alias, full_path in cb.get("file_aliases", {}).items():
        result = result.replace(alias, full_path)
    
    # 2. Decode symbols
    symbol_map = {
        "✓": "[PASS]", "✗": "[FAIL]", "⚠": "[PARTIAL]",
        "→": " nâng cấp thành ", "⊕": " tích hợp vào ",
        "Δ": "thay đổi ", "⛔": "[BLOCKED]",
        "G": "[GREEN]", "Y": "[YELLOW]", "R": "[RED]",
    }
    for sym, word in symbol_map.items():
        result = result.replace(sym, word)
    
    # 3. Decode prefixes
    for prefix, meaning in cb.get("prefixes", {}).items():
        if result.startswith(prefix):
            result = f"[{meaning}] {result[len(prefix):]}"
            break
    
    # 4. Decode domain aliases
    for code, full_term in cb.get("domain_aliases", {}).items():
        result = result.replace(code, full_term)
    
    # 5. Decode role aliases
    for code, full_role in cb.get("role_aliases", {}).items():
        result = result.replace(code, full_role)
    
    return result


# ══════════════════════════════════════════════════════════════════════════════
# ENGRAM ENCODER — Nén engram tự động
# ══════════════════════════════════════════════════════════════════════════════

def encode_engram(engram: dict) -> dict:
    """Nén 1 engram dict sang OpusLang v2 format."""
    category_map = {
        "lesson": "L", "session": "S", "error": "E",
        "pattern": "P", "handover": "H", "research": "R",
        "checkpoint": "C",
    }
    cat = category_map.get(engram.get("category", ""), "L")
    
    encoded_content = encode(engram.get("content", ""), category=cat)
    
    return {
        "id": engram.get("id", ""),
        "ts": engram.get("ts", ""),
        "v": "2",  # OpusLang version
        "c": encoded_content,  # Nội dung nén
        "tags": engram.get("tags", []),
    }


def decode_engram(encoded_engram: dict) -> dict:
    """Giải mã engram OpusLang v2 về dạng đọc được."""
    content = encoded_engram.get("c", encoded_engram.get("content", ""))
    return {
        "id": encoded_engram.get("id", ""),
        "ts": encoded_engram.get("ts", ""),
        "content": decode(content),
        "tags": encoded_engram.get("tags", []),
        "original_encoded": content,
    }


# ══════════════════════════════════════════════════════════════════════════════
# BATCH TOOLS — Nén/giải nén hàng loạt
# ══════════════════════════════════════════════════════════════════════════════

def compact_engrams(engrams_dir: str = None, dry_run: bool = True) -> dict:
    """
    Gộp engram cũ (>7 ngày) cùng category thành 1 engram nén.
    
    Args:
        engrams_dir: Path to .opus/engrams/
        dry_run: True = chỉ báo cáo, False = thực hiện gộp
    
    Returns:
        Report dict
    """
    if not engrams_dir:
        base = Path(__file__).resolve().parent.parent
        engrams_dir = base / ".opus" / "engrams"
    else:
        engrams_dir = Path(engrams_dir)
    
    if not engrams_dir.exists():
        return {"error": "Engrams directory not found"}
    
    now = datetime.now()
    by_category = {}
    fresh = []
    
    for f in engrams_dir.glob("*.json"):
        if f.name.startswith("_"):
            continue
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            ts = datetime.fromisoformat(data.get("ts", now.isoformat()))
            age_days = (now - ts).days
            
            if age_days >= 7:
                cat = data.get("category", "unknown")
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append({
                    "file": f.name,
                    "data": data,
                    "age_days": age_days,
                })
            else:
                fresh.append(f.name)
        except Exception:
            continue
    
    report = {
        "fresh_count": len(fresh),
        "compact_candidates": {cat: len(items) for cat, items in by_category.items()},
        "total_compactable": sum(len(v) for v in by_category.values()),
        "dry_run": dry_run,
    }
    
    if not dry_run and by_category:
        archive_dir = engrams_dir.parent / "archive"
        archive_dir.mkdir(exist_ok=True)
        
        for cat, items in by_category.items():
            # Encode tất cả thành 1 chuỗi nén
            encoded_parts = []
            for item in items:
                enc = encode(item["data"].get("content", ""), category=cat[0].upper())
                encoded_parts.append(enc)
            
            # Tạo 1 engram tổng hợp
            compact_id = f"compact_{cat}_{now.strftime('%Y%m%d')}"
            compact_engram = {
                "id": compact_id,
                "ts": now.isoformat(),
                "v": "2",
                "category": f"compact_{cat}",
                "c": " || ".join(encoded_parts),
                "source_count": len(items),
                "tags": ["compacted", cat],
            }
            
            # Lưu engram compact
            (engrams_dir / f"{compact_id}.json").write_text(
                json.dumps(compact_engram, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            
            # Archive originals
            for item in items:
                src = engrams_dir / item["file"]
                dst = archive_dir / item["file"]
                if src.exists():
                    src.rename(dst)
            
            report[f"compacted_{cat}"] = len(items)
    
    return report


def measure_compression(text: str) -> dict:
    """Đo tỷ lệ nén của 1 đoạn text."""
    original_tokens = len(text.split())
    encoded = encode(text)
    encoded_tokens = len(encoded.split())
    
    return {
        "original": text[:100] + "..." if len(text) > 100 else text,
        "encoded": encoded,
        "original_tokens": original_tokens,
        "encoded_tokens": encoded_tokens,
        "compression_ratio": round(1 - encoded_tokens / max(original_tokens, 1), 2),
    }


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("OpusLang v2.0 — Ngôn ngữ nén nội bộ Team Agentic AI")
        print()
        print("Cách dùng:")
        print('  python3 agentic/opuslang.py encode "Flash Brief #3: Nâng cấp Genesis VSA4..."')
        print('  python3 agentic/opuslang.py decode "L:F#3:@BRAIN→VSA4|✓"')
        print('  python3 agentic/opuslang.py measure "text dài cần đo nén"')
        print('  python3 agentic/opuslang.py compact [--execute]')
        print('  python3 agentic/opuslang.py alias "tools/A04_BRAIN_HELPER.py"')
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "encode" and len(sys.argv) > 2:
        text = " ".join(sys.argv[2:])
        result = encode(text)
        print(f"📥 Input:  {text}")
        print(f"📤 Output: {result}")
        print(f"📊 Nén: {len(text.split())} → {len(result.split())} tokens")
    
    elif cmd == "decode" and len(sys.argv) > 2:
        encoded = " ".join(sys.argv[2:])
        result = decode(encoded)
        print(f"📥 Encoded: {encoded}")
        print(f"📤 Decoded: {result}")
    
    elif cmd == "measure" and len(sys.argv) > 2:
        text = " ".join(sys.argv[2:])
        result = measure_compression(text)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif cmd == "compact":
        execute = "--execute" in sys.argv
        result = compact_engrams(dry_run=not execute)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif cmd == "alias" and len(sys.argv) > 2:
        filepath = sys.argv[2]
        alias = get_file_alias(filepath)
        print(f"{filepath} → {alias}")
    
    else:
        print(f"Lệnh không hợp lệ: {cmd}")
