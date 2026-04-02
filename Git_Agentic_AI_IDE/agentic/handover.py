"""
DNA Header v16.7 - Sovereign Purity
Role: HANDOVER (Bàn giao giữa các model — Opus ↔ Flash ↔ Gemini Pro)
Layer: 6 (Internal Team Agentic AI)

Handover Protocol — Tạo brief gọn khi chuyển task giữa models.
Giải quyết: Gemini Pro crash khi nhận conversation dài.
Giải pháp: Tạo handover brief NHẸ, paste vào conversation MỚI.

Cách dùng:
  python3 agentic/handover.py create "gemini_pro" "Phân tích lý thuyết VSA 5.0"
  python3 agentic/handover.py create "flash" "Thêm hàm mới vào Helper"
  python3 agentic/handover.py list
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HANDOVER_DIR = BASE_DIR / ".opus" / "handovers"
HANDOVER_DIR.mkdir(parents=True, exist_ok=True)

# Import OpusLang nếu có
try:
    sys.path.insert(0, str(Path(__file__).parent))
    from opuslang import load_codebook, encode, get_file_alias
    HAS_OPUSLANG = True
except ImportError:
    HAS_OPUSLANG = False


def _load_owner_profile() -> dict:
    """Nạp Owner Profile."""
    profile_path = BASE_DIR / ".opus" / "owner_profile.json"
    if profile_path.exists():
        return json.loads(profile_path.read_text(encoding='utf-8'))
    return {}


def _load_recent_engrams(n=5) -> list:
    """Nạp N engram gần nhất."""
    engram_dir = BASE_DIR / ".opus" / "engrams"
    if not engram_dir.exists():
        return []
    
    engrams = []
    for f in sorted(engram_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.name.startswith("_"):
            continue
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            engrams.append(data)
            if len(engrams) >= n:
                break
        except Exception:
            continue
    return engrams


def create_handover(
    target_model: str,
    task_description: str,
    files_relevant: list = None,
    context_notes: str = None,
) -> str:
    """
    Tạo handover brief cho model khác.
    
    Args:
        target_model: "flash" | "gemini_pro" | "opus"
        task_description: Mô tả task cần làm
        files_relevant: List file liên quan
        context_notes: Ghi chú thêm
    
    Returns:
        Path to handover file
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    handover_id = f"handover_{target_model}_{ts}"
    
    # Load context
    profile = _load_owner_profile()
    recent = _load_recent_engrams(5)
    
    # Build handover brief
    lines = []
    lines.append(f"# HANDOVER → {target_model.upper()}")
    lines.append(f"**ID:** `{handover_id}`")
    lines.append(f"**Từ:** Opus | **Lúc:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    
    # Owner context (cho mọi model biết cách làm việc với anh)
    if profile:
        lines.append("## Anh (Owner)")
        comm = profile.get("communication", {})
        lines.append(f"- Ngôn ngữ: {comm.get('language', 'vi')}")
        lines.append(f"- Style: {comm.get('style', 'ngắn gọn')}")
        lines.append(f"- Input: {comm.get('input_pattern', 'ý tưởng → team triển khai')}")
        prefs = profile.get("preferences", {})
        if prefs.get("dislikes"):
            lines.append(f"- ⛔ KHÔNG: {', '.join(prefs['dislikes'][:3])}")
        lines.append("")
    
    # Task
    lines.append("## Task")
    lines.append(task_description)
    lines.append("")
    
    # Files
    if files_relevant:
        lines.append("## Files liên quan")
        for f in files_relevant:
            alias = get_file_alias(f) if HAS_OPUSLANG else f
            lines.append(f"- `{f}` ({alias})")
        lines.append("")
    
    # Context từ engram gần nhất
    if recent:
        lines.append("## Context gần nhất (OpusLang v2)")
        for eng in recent[:3]:
            content = eng.get("c", eng.get("content", ""))
            if HAS_OPUSLANG and eng.get("v") != "2":
                content = encode(content)
            lines.append(f"- `{content[:120]}`")
        lines.append("")
    
    # Extra notes
    if context_notes:
        lines.append("## Ghi chú")
        lines.append(context_notes)
        lines.append("")
    
    # Model-specific instructions
    if target_model == "flash":
        lines.append("## Quy tắc Flash")
        lines.append("1. SCOPE_LOCK: Chỉ làm task trên, KHÔNG mở rộng")
        lines.append("2. Đầu phiên: `python3 agentic/task_anchor.py graph <file>`")
        lines.append("3. Cuối phiên: `python3 agentic/task_anchor.py check <file> <task>`")
        lines.append("4. Lưu engram: `python3 agentic/engram_rag.py learn \"tóm tắt\"`")
        lines.append("5. ⛔ XONG = DỪNG. Không tự ý làm thêm.")
    
    elif target_model == "gemini_pro":
        lines.append("## Quy tắc Gemini Pro")
        lines.append("1. Vai trò: THEORIST — phân tích lý thuyết, brainstorm, tìm edge cases")
        lines.append("2. Output: lưu vào `.opus/research/` dạng markdown")
        lines.append("3. KHÔNG code trực tiếp — chỉ viết spec/algorithm")
        lines.append("4. Khi xong: ghi tóm tắt 3 dòng cho Opus đọc")
    
    elif target_model == "opus":
        lines.append("## Quy tắc Opus")
        lines.append("1. Vai trò: ARCHITECT — thiết kế, plan, code phức tạp, verify")
        lines.append("2. Đọc Research Brief từ Gemini Pro (nếu có)")
        lines.append("3. Tạo Implementation Plan → xin LC phê duyệt")
        lines.append("4. Code hoặc tạo Flash Brief")
    
    content = "\n".join(lines)
    
    # Lưu file
    path = HANDOVER_DIR / f"{handover_id}.md"
    path.write_text(content, encoding='utf-8')
    
    # In ra cho Anh copy-paste
    print(f"✅ Handover đã tạo: {path}")
    print()
    print("=" * 60)
    print("COPY NỘI DUNG DƯỚI ĐÂY VÀO PHIÊN MỚI:")
    print("=" * 60)
    print(content)
    print("=" * 60)
    
    return str(path)


def list_handovers():
    """Liệt kê handover đã tạo."""
    if not HANDOVER_DIR.exists():
        print("Chưa có handover nào.")
        return
    
    handovers = sorted(HANDOVER_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not handovers:
        print("Chưa có handover nào.")
        return
    
    print(f"📋 Tổng: {len(handovers)} handover(s)\n")
    for h in handovers[:10]:
        size = h.stat().st_size
        print(f"  {h.name} ({size} bytes)")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Cách dùng:")
        print('  python3 agentic/handover.py create "flash" "Thêm hàm X vào file Y"')
        print('  python3 agentic/handover.py create "gemini_pro" "Phân tích lý thuyết Z"')
        print("  python3 agentic/handover.py list")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "create" and len(sys.argv) >= 4:
        target = sys.argv[2]
        task = sys.argv[3]
        files = sys.argv[4].split(",") if len(sys.argv) > 4 else None
        notes = sys.argv[5] if len(sys.argv) > 5 else None
        create_handover(target, task, files, notes)
    
    elif cmd == "list":
        list_handovers()
    
    else:
        print("Lệnh không hợp lệ.")
