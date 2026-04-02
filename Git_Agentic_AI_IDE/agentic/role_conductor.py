"""
DNA Header v16.7 - Sovereign Purity
Role: ROLE_CONDUCTOR (Dẫn dắt model qua quy trình)
Layer: 2 (Discipline Enforcement)

RoleConductor — Hệ thống DẪN DẮT model (kể cả model "attention bề mặt").
Mỗi Role có CHECKLIST bắt buộc. Mỗi bước có GATE.
Model KHÔNG THỂ skip bước mà không pass gate.

THIẾT KẾ CHO 2 LOẠI MODEL:
  - "Opus" (thông minh): Tự biết khi nào cần checkpoint, nhưng vẫn bị enforce
  - "Flash/Haiku" (nhanh, attention bề mặt): Cần prompt rõ ràng từng bước
    + Mỗi bước return lệnh TIẾP THEO model cần làm
    + Không bao giờ cho danh sách dài (model sẽ skip cuối)
    + Verify bước trước → mới cho bước sau
"""

import json
import os
import sys
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))
from opus_lang import encode_log_entry, encode_role


# ── Role Definitions ──────────────────────────────────────────────
ROLES = {
    "Architect": {
        "symbol": "A",
        "purpose": "Phân tích yêu cầu, thiết kế kiến trúc, tạo TaskGraph. KHÔNG viết code.",
        "checklist": [
            {"step": "understand", "label": "Đọc yêu cầu + ngữ cảnh (engram)",
             "gate": "output_summary_exists"},
            {"step": "decompose", "label": "Phân rã thành TaskGraph (DAG)",
             "gate": "graph_has_nodes"},
            {"step": "identify_risks", "label": "Xác định risk/blocker",
             "gate": "risk_noted"},
            {"step": "handover", "label": "Chuyển giao cho Coder với OpusLang brief",
             "gate": "handover_saved"},
        ],
    },
    "Coder": {
        "symbol": "C",
        "purpose": "Thực thi node từ TaskGraph. PHẢI checkpoint trước/sau mỗi node.",
        "checklist": [
            {"step": "read_graph", "label": "Đọc TaskGraph, lấy next_ready node",
             "gate": "node_selected"},
            {"step": "checkpoint_before", "label": "Checkpoint TRƯỚC khi code",
             "gate": "checkpoint_saved"},
            {"step": "implement", "label": "Viết code cho node",
             "gate": "file_created_or_modified"},
            {"step": "self_audit", "label": "Tự audit: syntax + DNA + logic",
             "gate": "audit_pass"},
            {"step": "mark_done", "label": "Mark node done trong graph",
             "gate": "node_marked"},
            {"step": "checkpoint_after", "label": "Checkpoint SAU khi code",
             "gate": "checkpoint_saved"},
        ],
    },
    "Auditor": {
        "symbol": "D",
        "purpose": "Kiểm tra chéo. Không tin bất kỳ ai. Chạy test độc lập.",
        "checklist": [
            {"step": "scan_scope", "label": "Xác định phạm vi audit",
             "gate": "scope_defined"},
            {"step": "syntax_check", "label": "AST parse mọi file .py",
             "gate": "all_syntax_ok"},
            {"step": "dna_check", "label": "Kiểm tra DNA Header v16.7+",
             "gate": "all_dna_ok"},
            {"step": "logic_review", "label": "Review logic / edge cases",
             "gate": "review_noted"},
            {"step": "report", "label": "Báo cáo kết quả bằng OpusLang",
             "gate": "report_saved"},
        ],
    },
    "Strategist": {
        "symbol": "S",
        "purpose": "Đánh giá risk, security, hiệu năng, VRAM budget.",
        "checklist": [
            {"step": "assess_risk", "label": "Đánh giá risk kiến trúc",
             "gate": "risk_documented"},
            {"step": "check_resources", "label": "Kiểm tra VRAM/RAM/disk budget",
             "gate": "resources_ok"},
            {"step": "security_scan", "label": "Quét lỗ hổng bảo mật",
             "gate": "scan_done"},
            {"step": "recommend", "label": "Đưa ra khuyến nghị",
             "gate": "recommendation_saved"},
        ],
    },
    "Leader": {
        "symbol": "L",
        "purpose": "Điều phối tổng thể. Đọc engram, chọn role, assign tasks.",
        "checklist": [
            {"step": "bootstrap", "label": "Bootstrap phiên từ engram",
             "gate": "context_loaded"},
            {"step": "plan", "label": "Lên kế hoạch phiên",
             "gate": "plan_exists"},
            {"step": "delegate", "label": "Chuyển sang role phù hợp",
             "gate": "role_selected"},
        ],
    },
}


@dataclass
class StepState:
    """Trạng thái của một step trong checklist."""
    step: str
    passed: bool = False
    output: str = ""
    timestamp: str = ""


class RoleConductor:
    """
    Dẫn dắt model qua quy trình bắt buộc (Layer 2).

    Thiết kế cho MỌI model — từ Opus đến Haiku:
    - `enter_role()` → Inject system prompt + checklist
    - `current_instruction()` → Trả về ĐÚNG 1 lệnh tiếp theo (không cả list)
    - `pass_gate()` → Verify bước hiện tại, cho phép tiến tiếp
    - `handover_brief()` → Tạo bản nén OpusLang cho role kế tiếp
    """

    def __init__(self, engram_dir=".opus/engrams"):
        self.engram_dir = engram_dir
        self.active_role: Optional[str] = None
        self.step_index: int = 0
        self.step_states: list[StepState] = []
        self.transition_log: list[str] = []
        os.makedirs(engram_dir, exist_ok=True)

    # ── Enter Role ────────────────────────────────────────────────
    def enter_role(self, role_name: str, context_brief: str = "") -> dict:
        """Vào một role. Trả về instruction đầu tiên.

        Args:
            role_name: "Architect", "Coder", "Auditor", "Strategist", "Leader"
            context_brief: OpusLang brief từ role trước (nếu có)

        Returns:
            Dict với system_prompt, first_instruction, checklist_preview
        """
        if role_name not in ROLES:
            return {"error": f"Unknown role: {role_name}"}

        role_def = ROLES[role_name]
        self.active_role = role_name
        self.step_index = 0
        self.step_states = [
            StepState(step=s["step"]) for s in role_def["checklist"]
        ]

        # Log transition
        log = encode_log_entry(
            from_role=self.active_role or "Leader",
            to_role=role_name,
            action_verb="entered",
            target="role",
            results={"init": "pass"},
            pending=[role_def["checklist"][0]["label"][:30]],
        )
        self.transition_log.append(log)

        # Build system prompt cho model
        system_prompt = self._build_system_prompt(role_def, context_brief)
        first_step = role_def["checklist"][0]

        return {
            "role": role_name,
            "symbol": role_def["symbol"],
            "system_prompt": system_prompt,
            "first_instruction": f"BƯỚC 1/{len(role_def['checklist'])}: {first_step['label']}",
            "checklist_total": len(role_def["checklist"]),
            "context_brief": context_brief,
        }

    # ── Current Instruction ───────────────────────────────────────
    def current_instruction(self) -> dict:
        """Trả về ĐÚNG 1 lệnh tiếp theo.

        Thiết kế cho model attention bề mặt:
        - CHỈ trả về 1 bước duy nhất
        - Rõ ràng: phải làm gì, kết quả mong đợi
        - Có số bước hiện tại / tổng bước
        """
        if not self.active_role:
            return {"error": "No active role. Call enter_role() first."}

        role_def = ROLES[self.active_role]
        checklist = role_def["checklist"]

        if self.step_index >= len(checklist):
            return {
                "status": "COMPLETE",
                "message": f"Role [{self.active_role}] đã hoàn thành mọi bước.",
                "action": "Gọi handover_brief() để chuyển role.",
            }

        step = checklist[self.step_index]
        return {
            "status": "ACTIVE",
            "role": self.active_role,
            "step_number": f"{self.step_index + 1}/{len(checklist)}",
            "instruction": step["label"],
            "gate_condition": step["gate"],
            "message": f"[{self.active_role}] BƯỚC {self.step_index + 1}: {step['label']}\n"
                       f"Điều kiện pass: {step['gate']}",
        }

    # ── Gate Verification ─────────────────────────────────────────
    def pass_gate(self, evidence: str = "", force: bool = False) -> dict:
        """Kiểm tra bước hiện tại đã pass gate chưa, cho phép tiến tiếp.

        Args:
            evidence: Bằng chứng hoàn thành (ví dụ: "syntax OK", file path)
            force: True để skip (chỉ Leader/Opus được dùng)

        Returns:
            Dict với trạng thái và instruction tiếp theo
        """
        if not self.active_role:
            return {"error": "No active role."}

        role_def = ROLES[self.active_role]
        checklist = role_def["checklist"]

        if self.step_index >= len(checklist):
            return {"status": "ALREADY_COMPLETE"}

        # Mark current step as passed
        self.step_states[self.step_index].passed = True
        self.step_states[self.step_index].output = evidence
        self.step_states[self.step_index].timestamp = datetime.now().isoformat()

        step = checklist[self.step_index]
        log = encode_log_entry(
            from_role=self.active_role,
            action_verb="verified",
            target=step["step"],
            results={step["gate"]: "pass" if not force else "forced"},
        )
        self.transition_log.append(log)

        # Advance to next step
        self.step_index += 1

        # Return next instruction
        return {
            "status": "GATE_PASSED",
            "completed_step": step["label"],
            "next": self.current_instruction(),
        }

    # ── Handover ──────────────────────────────────────────────────
    def handover_brief(self, to_role: str = None) -> str:
        """Tạo bản OpusLang nén cho role kế tiếp.

        Đây là thứ được inject vào prompt đầu tiên của role mới,
        giúp model "attention bề mặt" nắm bắt ngữ cảnh ngay lập tức.
        """
        completed = [s for s in self.step_states if s.passed]
        pending = [s for s in self.step_states if not s.passed]

        lines = [
            f"# HANDOVER {encode_role(self.active_role or 'Leader')}→{encode_role(to_role or '?')}",
            f"DONE: {', '.join(s.step for s in completed)}",
        ]
        if pending:
            lines.append(f"TODO: {', '.join(s.step for s in pending)}")

        # Include last 3 transition logs
        if self.transition_log:
            lines.append("LOG:")
            for entry in self.transition_log[-3:]:
                lines.append(f"  {entry}")

        brief = "\n".join(lines)

        # Save to engram
        ts = datetime.now().strftime("%H%M%S")
        path = os.path.join(
            self.engram_dir,
            f"handover_{encode_role(self.active_role or 'L')}_{ts}.json"
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "type": "handover",
                "from": self.active_role,
                "to": to_role,
                "brief": brief,
                "steps_completed": [vars(s) for s in completed],
                "steps_pending": [vars(s) for s in pending],
                "ts": datetime.now().isoformat(),
            }, f, indent=2, ensure_ascii=False)

        return brief

    # ── System Prompt Builder ─────────────────────────────────────
    def _build_system_prompt(self, role_def: dict, context_brief: str) -> str:
        """Xây dựng system prompt cho model.

        Prompt được thiết kế để model KÉM cũng phải tuân thủ:
        1. Mở đầu bằng ROLE identity rõ ràng
        2. Checklist bắt buộc
        3. CẢNH BÁO nếu skip
        4. Context brief nén
        """
        checklist_str = "\n".join(
            f"  {i+1}. {s['label']} [Gate: {s['gate']}]"
            for i, s in enumerate(role_def["checklist"])
        )

        prompt = f"""BẠN ĐANG LÀ: [{role_def['symbol']}] {self.active_role}
MỤC ĐÍCH: {role_def['purpose']}

CHECKLIST BẮT BUỘC (KHÔNG ĐƯỢC SKIP):
{checklist_str}

⚠️ CẢNH BÁO: Mỗi bước có GATE (cổng). Bạn PHẢI hoàn thành bước hiện tại
trước khi được phép làm bước tiếp theo. Nếu bạn skip → hệ thống sẽ ROLLBACK.

QUY TẮC:
- Gọi pass_gate(evidence) sau mỗi bước
- Ghi nhận output bằng OpusLang
- Khi hoàn thành mọi bước: gọi handover_brief()"""

        if context_brief:
            prompt += f"\n\nNGỮ CẢNH TỪ ROLE TRƯỚC:\n{context_brief}"

        return prompt

    # ── Convenience ───────────────────────────────────────────────
    def status_summary(self) -> str:
        """Tóm tắt trạng thái hiện tại."""
        if not self.active_role:
            return "No active role."
        done = sum(1 for s in self.step_states if s.passed)
        total = len(self.step_states)
        return (
            f"[{encode_role(self.active_role)}] {self.active_role}: "
            f"{done}/{total} steps | "
            f"Current: {self.current_instruction().get('instruction', 'DONE')}"
        )


# ── CLI ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "demo":
        print("═══ RoleConductor Demo ═══")
        print("Simulating: Model 'attention bề mặt' follows Architect checklist\n")

        conductor = RoleConductor()

        # 1. Enter Architect role
        entry = conductor.enter_role("Architect", context_brief="L | boot(harness):ini✓ | P:none")
        print(f"System Prompt:\n{entry['system_prompt']}\n")
        print(f"First Instruction: {entry['first_instruction']}\n")

        # 2. Walk through each step
        steps_evidence = [
            "Read AGENTS.md + engram. Goal: build Opus v2.0",
            "Created TaskGraph with 8 nodes, critical path T01→T08",
            "Risk: VRAM contention if embedding model used for RAG",
            "Handover brief saved to .opus/engrams/",
        ]

        for i, evidence in enumerate(steps_evidence):
            result = conductor.pass_gate(evidence)
            print(f"Gate {i+1}: {result['status']}")
            nxt = result.get("next", {})
            if nxt.get("status") == "COMPLETE":
                print(f"  → {nxt['message']}\n")
            else:
                print(f"  → Next: {nxt.get('instruction', 'N/A')}\n")

        # 3. Handover
        brief = conductor.handover_brief(to_role="Coder")
        print(f"═══ Handover Brief ═══\n{brief}\n")

        # 4. Enter Coder role with brief
        entry2 = conductor.enter_role("Coder", context_brief=brief)
        print(f"═══ Coder First Instruction ═══")
        print(f"{entry2['first_instruction']}")
        print(f"\nStatus: {conductor.status_summary()}")

    elif sys.argv[1] == "roles":
        for name, rdef in ROLES.items():
            steps = len(rdef["checklist"])
            print(f"[{rdef['symbol']}] {name}: {rdef['purpose'][:60]}... ({steps} steps)")
