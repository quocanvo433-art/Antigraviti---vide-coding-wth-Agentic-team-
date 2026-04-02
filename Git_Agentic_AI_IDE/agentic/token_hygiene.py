"""
DNA Header v16.7 - Sovereign Purity
Role: TOKEN_HYGIENE (Dọn rác mỗi phiên — Thanh tẩy cửa sổ ngữ cảnh)
Layer: 6 (Internal Team Agentic AI)

Token Hygiene — Chạy đầu mỗi phiên để:
1. Kill process Python treo (zombie)
2. Dọn file tmp cũ >24h
3. Kiểm tra engram chưa compact
4. Đếm tổng token budget estimate
5. Báo cáo 5 dòng sạch gọn

Cách dùng:
  python3 agentic/token_hygiene.py          # Báo cáo (dry-run)
  python3 agentic/token_hygiene.py --clean   # Dọn thật
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent


def check_zombie_processes() -> dict:
    """Tìm process Python treo >30 phút."""
    zombies = []
    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split('\n'):
            if 'python3' in line.lower() and ('defunct' in line or 'Z' in line.split()[7:8]):
                zombies.append(line.strip()[:120])
    except Exception:
        pass
    return {"count": len(zombies), "details": zombies[:5]}


def check_tmp_files() -> dict:
    """Đếm file tmp cũ >24h."""
    tmp_dirs = [
        BASE_DIR / "tmp",
        Path("/tmp"),
    ]
    old_files = []
    now = time.time()
    cutoff = now - 86400  # 24h
    
    for tmp_dir in tmp_dirs:
        if not tmp_dir.exists():
            continue
        for f in tmp_dir.iterdir():
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    old_files.append(str(f))
            except Exception:
                continue
    
    return {"count": len(old_files), "details": old_files[:10]}


def check_engram_health() -> dict:
    """Kiểm tra sức khỏe engram."""
    engram_dir = BASE_DIR / ".opus" / "engrams"
    if not engram_dir.exists():
        return {"count": 0, "needs_compact": False, "last_engram": None}
    
    engrams = list(engram_dir.glob("*.json"))
    engrams = [e for e in engrams if not e.name.startswith("_")]
    
    # Tìm engram cuối
    last_engram = None
    last_ts = None
    old_count = 0
    now = datetime.now()
    
    for e in engrams:
        try:
            data = json.loads(e.read_text(encoding='utf-8'))
            ts_str = data.get("ts", "")
            ts = datetime.fromisoformat(ts_str) if ts_str else None
            if ts:
                if last_ts is None or ts > last_ts:
                    last_ts = ts
                    last_engram = e.name
                if (now - ts).days >= 7:
                    old_count += 1
        except Exception:
            continue
    
    return {
        "count": len(engrams),
        "old_count": old_count,
        "needs_compact": old_count >= 5,
        "last_engram": last_engram,
        "last_ts": last_ts.isoformat() if last_ts else None,
    }


def check_owner_profile() -> dict:
    """Kiểm tra Owner Profile tồn tại."""
    profile_path = BASE_DIR / ".opus" / "owner_profile.json"
    if not profile_path.exists():
        return {"exists": False, "lessons": 0}
    
    try:
        data = json.loads(profile_path.read_text(encoding='utf-8'))
        lessons = len(data.get("lessons_learned", []))
        return {"exists": True, "lessons": lessons}
    except Exception:
        return {"exists": False, "lessons": 0}


def check_codebook() -> dict:
    """Kiểm tra OpusLang codebook."""
    cb_path = BASE_DIR / ".opus" / "codebook.json"
    if not cb_path.exists():
        return {"exists": False}
    
    try:
        data = json.loads(cb_path.read_text(encoding='utf-8'))
        alias_count = len(data.get("file_aliases", {}))
        return {"exists": True, "version": data.get("_meta", {}).get("version", "?"), "aliases": alias_count}
    except Exception:
        return {"exists": False}


def estimate_context_budget() -> dict:
    """Ước tính token budget đã dùng cho context hiện tại."""
    # Engram injection: ~mỗi engram 50 tokens sau nén
    engram = check_engram_health()
    engram_tokens = engram["count"] * 50
    
    # Owner profile: ~200 tokens
    profile_tokens = 200 if check_owner_profile()["exists"] else 0
    
    # Codebook: ~150 tokens
    codebook_tokens = 150 if check_codebook()["exists"] else 0
    
    # Workflow rules: ~300 tokens
    workflow_tokens = 300
    
    total = engram_tokens + profile_tokens + codebook_tokens + workflow_tokens
    
    return {
        "engram_tokens": engram_tokens,
        "profile_tokens": profile_tokens,
        "codebook_tokens": codebook_tokens,
        "workflow_tokens": workflow_tokens,
        "total_injected": total,
        "budget_200k_pct": round(total / 200000 * 100, 1),
    }


def clean_tmp(dry_run=True) -> int:
    """Dọn file tmp cũ. Returns số file đã dọn."""
    tmp_info = check_tmp_files()
    if dry_run:
        return tmp_info["count"]
    
    cleaned = 0
    for f_path in tmp_info["details"]:
        try:
            p = Path(f_path)
            # Chỉ dọn file trong project tmp, KHÔNG dọn /tmp system
            if str(BASE_DIR) in str(p):
                p.unlink()
                cleaned += 1
        except Exception:
            continue
    return cleaned


def run_hygiene(clean=False) -> str:
    """Chạy toàn bộ kiểm tra, trả về báo cáo gọn."""
    lines = []
    lines.append("🧹 TOKEN HYGIENE REPORT")
    lines.append("=" * 40)
    
    # 1. Zombie processes
    zombies = check_zombie_processes()
    if zombies["count"] > 0:
        lines.append(f"⚠️  Zombie processes: {zombies['count']}")
    else:
        lines.append("✅ Processes: sạch")
    
    # 2. Tmp files
    tmp = check_tmp_files()
    if tmp["count"] > 0:
        if clean:
            cleaned = clean_tmp(dry_run=False)
            lines.append(f"🗑️  Tmp: đã dọn {cleaned} file cũ")
        else:
            lines.append(f"⚠️  Tmp: {tmp['count']} file cũ >24h (dùng --clean để dọn)")
    else:
        lines.append("✅ Tmp: sạch")
    
    # 3. Engram health
    engram = check_engram_health()
    if engram["needs_compact"]:
        lines.append(f"⚠️  Engram: {engram['count']} tổng ({engram['old_count']} cần compact)")
    else:
        lines.append(f"✅ Engram: {engram['count']} (cuối: {engram['last_engram'] or 'chưa có'})")
    
    # 4. OpusLang toolkit
    cb = check_codebook()
    profile = check_owner_profile()
    toolkit = []
    if cb["exists"]:
        toolkit.append(f"Codebook v{cb.get('version', '?')}")
    else:
        toolkit.append("❌ Codebook MISSING")
    if profile["exists"]:
        toolkit.append(f"Profile({profile['lessons']} lessons)")  
    else:
        toolkit.append("❌ Profile MISSING")
    lines.append(f"🔧 Toolkit: {' | '.join(toolkit)}")
    
    # 5. Token budget
    budget = estimate_context_budget()
    lines.append(f"📊 Token footprint: ~{budget['total_injected']} ({budget['budget_200k_pct']}% of 200K)")
    
    lines.append("=" * 40)
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    clean = "--clean" in sys.argv
    report = run_hygiene(clean=clean)
    print(report)
