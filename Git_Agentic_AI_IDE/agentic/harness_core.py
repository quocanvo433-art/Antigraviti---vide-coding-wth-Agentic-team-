"""
DNA Header v16.7 - Sovereign Purity
Role: HARNESS_CORE (Lõi điều phối trung tâm)
Layer: 1 (Foundation)

HarnessCore — Bộ não điều phối của mọi phiên Opus.
Cung cấp: bootstrap, checkpoint/rollback, audit, session summary.
Mọi layer khác đều gọi qua HarnessCore.
"""

import ast
import json
import os
import sys
from datetime import datetime
from uuid import uuid4

# Import OpusLang (Layer 5 — foundation protocol)
sys.path.insert(0, os.path.dirname(__file__))
from opus_lang import encode_log_entry, encode_session_summary, decode_entry


class HarnessCore:
    """
    Lõi điều phối trung tâm (Layer 1).

    Trách nhiệm:
    - Bootstrap phiên: nạp engram gần nhất, role hiện tại, pending tasks
    - Checkpoint (Lỗ giun): lưu reasoning state
    - Rollback: quay về điểm neo
    - Audit: kiểm tra AST + DNA trên file Python
    - Session summary: nén phiên thành OpusLang
    """

    def __init__(self, opus_dir=".opus", engram_dir=None):
        self.opus_dir = opus_dir
        self.engram_dir = engram_dir or os.path.join(opus_dir, "engrams")
        self.session_log = []  # OpusLang entries for this session
        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(self.engram_dir, exist_ok=True)

    # ── Bootstrap ─────────────────────────────────────────────────
    def bootstrap(self) -> dict:
        """Khởi động phiên. Trả về context tối thiểu cho model."""
        latest_engram = self._latest_engram()
        current_role = self._current_role()
        pending = self._pending_from_engram(latest_engram)

        context = {
            "session_id": uuid4().hex[:8],
            "timestamp": datetime.now().isoformat(),
            "current_role": current_role,
            "latest_engram": latest_engram,
            "pending_tasks": pending,
            "harness_version": "v2.0",
        }

        self._log("Leader", None, "bootstrap", "harness",
                  {"init": "pass"}, pending[:3] if pending else [])
        return context

    # ── Checkpoint (Lỗ giun) ──────────────────────────────────────
    def checkpoint(self, role: str, reasoning: str,
                   status: str = "success", tags: list = None) -> str:
        """Lưu một điểm neo tư duy.

        Args:
            role: Role hiện tại (e.g., "Architect")
            reasoning: Mô tả ngắn gọn trạng thái tư duy
            status: "success" | "warning" | "error"
            tags: Tags cho Engram RAG (Layer 4) tìm kiếm

        Returns:
            checkpoint_id
        """
        cp_id = uuid4().hex[:8]
        data = {
            "type": "checkpoint",
            "id": cp_id,
            "ts": datetime.now().isoformat(),
            "role": role,
            "reasoning": reasoning,
            "status": status,
            "tags": tags or [],
            "session_log_snapshot": self.session_log.copy(),
        }
        path = os.path.join(self.engram_dir, f"cp_{cp_id}.json")
        self._write_json(path, data)

        self._log(role, None, "checkpoint", f"cp_{cp_id}",
                  {"status": status}, [])
        return cp_id

    def rollback(self, checkpoint_id: str) -> dict:
        """Quay về một điểm neo."""
        path = os.path.join(self.engram_dir, f"cp_{checkpoint_id}.json")
        if not os.path.exists(path):
            return {"error": f"Checkpoint {checkpoint_id} not found"}
        data = self._read_json(path)
        self.session_log = data.get("session_log_snapshot", [])
        self._log("Leader", None, "rollback", f"cp_{checkpoint_id}",
                  {"status": "pass"}, [])
        return data

    # ── Audit ─────────────────────────────────────────────────────
    def audit(self, file_path: str) -> dict:
        """Kiểm tra AST + DNA trên file Python.

        Returns:
            {"syntax": True/False, "dna": True/False, "details": str}
        """
        result = {"file": file_path, "syntax": False, "dna": False, "details": ""}

        # Syntax check via AST
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            ast.parse(source)
            result["syntax"] = True
        except SyntaxError as e:
            result["details"] = f"SyntaxError: {e.msg} (line {e.lineno})"
            return result
        except Exception as e:
            result["details"] = f"ReadError: {str(e)}"
            return result

        # DNA check
        if 'DNA Header' in source and 'Sovereign Purity' in source:
            result["dna"] = True
        else:
            result["details"] = "DNA Header missing or incomplete"

        return result

    def audit_directory(self, dir_path: str, pattern: str = "*.py") -> list:
        """Audit tất cả file Python trong một thư mục."""
        import glob
        results = []
        for fpath in sorted(glob.glob(os.path.join(dir_path, pattern))):
            results.append(self.audit(fpath))
        return results

    # ── Session Summary ───────────────────────────────────────────
    def session_summary(self) -> str:
        """Trả về toàn bộ session dưới dạng OpusLang nén."""
        return "\n".join(self.session_log)

    def close_session(self, essence: str = None) -> str:
        """Đóng phiên, lưu summary vào engram.

        Args:
            essence: Sovereign Essence (25 từ tóm tắt phiên)

        Returns:
            Path to saved session engram
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        data = {
            "type": "session",
            "ts": ts,
            "log": self.session_log,
            "log_opuslang": self.session_summary(),
            "essence": essence or "No essence provided",
        }
        path = os.path.join(self.engram_dir, f"session_{ts}.json")
        self._write_json(path, data)
        return path

    # ── Internal Helpers ──────────────────────────────────────────
    def _log(self, from_role, to_role, verb, target, results, pending):
        """Append OpusLang entry to session log."""
        entry = encode_log_entry(
            from_role=from_role, to_role=to_role,
            action_verb=verb, target=target,
            results=results, pending=pending,
            timestamp=True,
        )
        self.session_log.append(entry)

    def _latest_engram(self) -> dict:
        """Get the most recent engram."""
        engrams = []
        for f in os.listdir(self.engram_dir):
            if f.endswith(".json") and not f.startswith("_"):
                try:
                    data = self._read_json(os.path.join(self.engram_dir, f))
                    engrams.append(data)
                except Exception:
                    continue
        if not engrams:
            return {}
        # Sort by timestamp field (various formats)
        return max(engrams, key=lambda x: x.get("ts", x.get("timestamp", "")))

    def _current_role(self) -> str:
        """Get current active role."""
        role_file = os.path.join(self.engram_dir, "current_role.json")
        if os.path.exists(role_file):
            data = self._read_json(role_file)
            return data.get("role", "Leader")
        return "Leader"

    def _pending_from_engram(self, engram: dict) -> list:
        """Extract pending tasks from latest engram."""
        if not engram:
            return []
        # Try to parse from OpusLang log
        log = engram.get("log_opuslang", "")
        if log:
            for line in reversed(log.split("\n")):
                decoded = decode_entry(line)
                if decoded.get("pending"):
                    return decoded["pending"]
        return engram.get("pending", [])

    @staticmethod
    def _write_json(path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _read_json(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


# ── CLI ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    harness = HarnessCore()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 harness_core.py bootstrap")
        print("  python3 harness_core.py audit <file.py>")
        print("  python3 harness_core.py audit-dir <dir/>")
        print("  python3 harness_core.py checkpoint <role> <reasoning>")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "bootstrap":
        ctx = harness.bootstrap()
        print(json.dumps(ctx, indent=2, ensure_ascii=False))
        print(f"\nSession Log (OpusLang):\n{harness.session_summary()}")

    elif cmd == "audit" and len(sys.argv) >= 3:
        result = harness.audit(sys.argv[2])
        syn = "✓" if result["syntax"] else "✗"
        dna = "✓" if result["dna"] else "✗"
        print(f"Audit {result['file']}: syn{syn} dna{dna}")
        if result["details"]:
            print(f"  Details: {result['details']}")

    elif cmd == "audit-dir" and len(sys.argv) >= 3:
        results = harness.audit_directory(sys.argv[2])
        total = len(results)
        syn_ok = sum(1 for r in results if r["syntax"])
        dna_ok = sum(1 for r in results if r["dna"])
        print(f"Audit {sys.argv[2]}: {total} files")
        print(f"  Syntax: {syn_ok}/{total}  DNA: {dna_ok}/{total}")
        for r in results:
            syn = "✓" if r["syntax"] else "✗"
            dna = "✓" if r["dna"] else "✗"
            status = f"syn{syn} dna{dna}"
            name = os.path.basename(r["file"])
            print(f"  {name}: {status}")

    elif cmd == "checkpoint" and len(sys.argv) >= 4:
        cp_id = harness.checkpoint(sys.argv[2], sys.argv[3])
        print(f"Checkpoint saved: {cp_id}")
        print(f"Session Log:\n{harness.session_summary()}")
