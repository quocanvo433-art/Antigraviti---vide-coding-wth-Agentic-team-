"""
DNA Header v16.7 - Sovereign Purity
Role: FLASH_BRIEF (Công cụ tạo brief nén cho Flash)
Layer: 2.5 (Bridge giữa Opus plan → Flash exec)

FlashBrief — Tạo bản giao việc siêu nén cho Flash model.
Flash attention bề mặt → Brief phải ngắn, cụ thể, không mơ hồ.
Mỗi brief = 1 file markdown trong .opus/briefs/
"""

import json
import os
import sys
from datetime import datetime

BRIEF_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".opus", "briefs"
)
os.makedirs(BRIEF_DIR, exist_ok=True)


def create_brief(
    muc_tieu: str,
    file_target: str,
    cac_buoc: list,
    kiem_tra: list = None,
    ngon_ngu: str = "vi",
    plan_ref: str = None,
) -> str:
    """Tạo brief nén cho Flash.

    Args:
        muc_tieu: 1 câu mô tả mục tiêu (VD: "Thêm hàm calculate_kinematics vào Helper")
        file_target: Đường dẫn file cần sửa
        cac_buoc: List các bước cụ thể (mỗi bước = 1 string)
        kiem_tra: List các lệnh kiểm tra sau khi xong
        ngon_ngu: "vi" (mặc định tiếng Việt)
        plan_ref: Link tới Implementation Plan (nếu có)

    Returns:
        Đường dẫn file brief đã tạo
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    brief_id = f"brief_{ts}"

    # Tạo nội dung brief
    lines = []
    lines.append("# FLASH BRIEF — TỪ OPUS")
    lines.append(f"**ID:** `{brief_id}`")
    lines.append(f"**Thời gian:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if plan_ref:
        lines.append(f"**Plan gốc:** {plan_ref}")
    lines.append("")

    lines.append(f"## MỤC TIÊU")
    lines.append(f"{muc_tieu}")
    lines.append("")

    lines.append(f"## FILE TARGET")
    lines.append(f"`{file_target}`")
    lines.append("")

    lines.append("## CÁC BƯỚC THỰC HIỆN")
    for i, buoc in enumerate(cac_buoc, 1):
        lines.append(f"{i}. {buoc}")
    lines.append("")

    if kiem_tra:
        lines.append("## KIỂM TRA SAU KHI XONG")
        for kt in kiem_tra:
            lines.append(f"- `{kt}`")
        lines.append("")

    lines.append("## ĐẦU PHIÊN (BẮT BUỘC)")
    lines.append(f"```bash")
    lines.append(f"python3 agentic/task_anchor.py graph \"{file_target}\"")
    lines.append(f"```")
    lines.append("Đọc output để biết: file này ảnh hưởng ai, ai ảnh hưởng nó, hàm nào KHÔNG được đổi tên.")
    lines.append("")

    lines.append("## QUY TẮC BẮT BUỘC")
    lines.append("- [ ] Code theo đúng spec — KHÔNG tự ý thay đổi kiến trúc")
    lines.append("- [ ] Giao tiếp bằng **tiếng Việt**")
    lines.append("- [ ] Chạy audit: `python3 agentic/harness_core.py audit <file>`")
    lines.append('- [ ] Cuối phiên: `python3 agentic/engram_rag.py learn "tóm tắt"`')
    lines.append("- [ ] Nếu gặp quyết định kiến trúc → DỪNG, báo **CẦN OPUS**")
    lines.append("")
    lines.append("## ⚓ NEO DỪNG (ANCHOR CHECK)")
    lines.append("Sau khi hoàn tất, chạy lệnh này. Nếu ra 🟢 GREEN → DỪNG PHIÊN ngay:")
    lines.append(f"```bash")
    lines.append(f"python3 agentic/task_anchor.py check \"{file_target}\" \"{muc_tieu}\"")
    lines.append(f"```")
    lines.append("- 🟢 **GREEN** = Đã đủ. BÀN GIAO AN TOÀN. **DỪNG NGAY.**")
    lines.append("- 🟡 **YELLOW** = Xem lại trước khi bàn giao.")
    lines.append("- 🔴 **RED** = Lỗi! Sửa trước khi bàn giao.")
    lines.append("")
    lines.append("## ⛔ LỆNH DỪNG (SCOPE_LOCK)")
    lines.append("- **KHI ANCHOR = GREEN: DỪNG. KHÔNG TỰ Ý LÀM BRIEF KHÁC.**")
    lines.append("- **KHÔNG MỞ FILE PLAN ĐỂ ĐỌC TASK KẾ TIẾP.**")
    lines.append("- **Trả kết quả cho Anh, chờ lệnh mới.**")

    content = "\n".join(lines)

    # Lưu file
    path = os.path.join(BRIEF_DIR, f"{brief_id}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    # In ra stdout để Anh copy-paste vào Flash
    print(f"✅ Brief đã tạo: {path}\n")
    print("=" * 60)
    print("COPY NỘI DUNG DƯỚI ĐÂY VÀO PHIÊN FLASH:")
    print("=" * 60)
    print(content)
    print("=" * 60)

    return path


def list_briefs():
    """Liệt kê tất cả brief đã tạo."""
    if not os.path.exists(BRIEF_DIR):
        print("Chưa có brief nào.")
        return

    briefs = sorted(os.listdir(BRIEF_DIR), reverse=True)
    if not briefs:
        print("Chưa có brief nào.")
        return

    print(f"📋 Tổng cộng: {len(briefs)} brief(s)\n")
    for b in briefs[:10]:
        path = os.path.join(BRIEF_DIR, b)
        size = os.path.getsize(path)
        print(f"  {b} ({size} bytes)")


# ── CLI ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Cách dùng:")
        print('  python3 flash_brief.py create "mục tiêu" "file_target" "bước1|bước2|bước3"')
        print("  python3 flash_brief.py list")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "create" and len(sys.argv) >= 5:
        muc_tieu = sys.argv[2]
        file_target = sys.argv[3]
        cac_buoc = sys.argv[4].split("|")
        kiem_tra = sys.argv[5].split("|") if len(sys.argv) > 5 else None
        create_brief(muc_tieu, file_target, cac_buoc, kiem_tra)

    elif cmd == "list":
        list_briefs()

    else:
        print("Lệnh không hợp lệ. Chạy không tham số để xem hướng dẫn.")
