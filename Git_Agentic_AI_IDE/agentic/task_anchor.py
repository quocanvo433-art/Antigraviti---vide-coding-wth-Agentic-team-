"""
DNA Header v16.7 - Sovereign Purity
Role: TASK_ANCHOR (Neo Phiên — Cơ chế tự kiểm tra cho Flash)
Layer: 2.5 (Bridge giữa Brief → Execution → Verification)

Task Anchor — "Làm tốt chính là làm ĐỦ phần của mình"

Triết lý:
- Flash nhanh nhảu → cần "neo" để dừng lại đúng lúc
- Neo = kiểm tra 3 câu hỏi:
  1. MỤC TIÊU brief đã đạt chưa? (output match spec)
  2. PHẠM VI có bị vượt không? (chỉ sửa đúng file target)
  3. XUNG QUANH có bị phá không? (file liên quan vẫn import OK)

Cách dùng:
  # Đầu phiên Flash — nạp context vừa đủ:
  python3 agentic/task_anchor.py load "tools/A04_BRAIN_HELPER.py"
  
  # Cuối phiên Flash — kiểm tra neo:
  python3 agentic/task_anchor.py check "tools/A04_BRAIN_HELPER.py" "Thêm 6 hàm Kinematics"
"""

import os
import sys
import json
import ast
import importlib.util
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# ══════════════════════════════════════════════════════════════════════════════
# 1. CONTEXT LOADER — "Biết đủ, không biết thừa"
# ══════════════════════════════════════════════════════════════════════════════

def load_bounded_context(file_target: str) -> dict:
    """
    Tạo "bản đồ nhận thức giới hạn" cho Flash.
    Flash chỉ nhận được:
    - File target: cấu trúc (tên hàm, class, import)
    - Láng giềng trực tiếp: file nào import file target?
    - Ràng buộc: hàm nào từ file target đang được dùng ở nơi khác?
    
    Flash KHÔNG nhận: nội dung chi tiết file khác, implementation plan, brief khác.
    """
    target_path = BASE_DIR / file_target
    if not target_path.exists():
        return {"error": f"File không tồn tại: {file_target}"}
    
    context = {
        "file_target": file_target,
        "structure": _extract_structure(target_path),
        "neighbors": _find_importers(file_target),
        "constraints": _find_usage_constraints(file_target),
    }
    
    return context


def _extract_structure(filepath: Path) -> dict:
    """Trích xuất cấu trúc file: tên hàm, class, biến global, import."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except SyntaxError as e:
        return {"error": f"Syntax error: {e}"}
    
    functions = []
    classes = []
    imports = []
    constants = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "args": [a.arg for a in node.args.args],
            })
        elif isinstance(node, ast.ClassDef):
            classes.append({"name": node.name, "line": node.lineno})
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            else:
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    constants.append(target.id)
    
    return {
        "functions": [f["name"] for f in functions],
        "function_details": functions[:30],  # Giới hạn 30 hàm
        "classes": classes,
        "imports": imports[:20],
        "constants": constants[:20],
        "total_functions": len(functions),
        "total_lines": len(open(filepath).readlines()),
    }


def _find_importers(file_target: str) -> list:
    """Tìm tất cả file TRỰC TIẾP import file target."""
    target_module = Path(file_target).stem  # VD: "A04_BRAIN_HELPER"
    importers = []
    
    search_dirs = [
        BASE_DIR / "agents" / "logic",
        BASE_DIR / "tools",
        BASE_DIR / "agentic",
    ]
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for py_file in search_dir.glob("*.py"):
            try:
                content = py_file.read_text(encoding='utf-8')
                if f"import {target_module}" in content or f"from {target_module}" in content:
                    # Tìm chính xác dòng import
                    for i, line in enumerate(content.split('\n'), 1):
                        if target_module in line and ('import' in line):
                            importers.append({
                                "file": str(py_file.relative_to(BASE_DIR)),
                                "line": i,
                                "import_statement": line.strip(),
                            })
            except Exception:
                continue
    
    return importers


def _find_usage_constraints(file_target: str) -> list:
    """Tìm hàm nào từ file target đang được GỌI ở file khác → ràng buộc không được đổi API."""
    target_path = BASE_DIR / file_target
    if not target_path.exists():
        return []
    
    # Lấy tên tất cả hàm public trong file target
    try:
        with open(target_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except SyntaxError:
        return []
    
    public_funcs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
            public_funcs.append(node.name)
    
    constraints = []
    search_dirs = [BASE_DIR / "agents" / "logic", BASE_DIR / "tools"]
    
    for func_name in public_funcs[:20]:  # Giới hạn 20 hàm public
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for py_file in search_dir.glob("*.py"):
                if py_file.name == Path(file_target).name:
                    continue  # Bỏ qua chính nó
                try:
                    content = py_file.read_text(encoding='utf-8')
                    if func_name in content:
                        constraints.append({
                            "function": func_name,
                            "used_in": str(py_file.relative_to(BASE_DIR)),
                            "warning": f"⚠️ HÀM {func_name}() đang được dùng bởi file khác — KHÔNG đổi signature!",
                        })
                except Exception:
                    continue
    
    return constraints


# ══════════════════════════════════════════════════════════════════════════════
# 2. ANCHOR CHECK — "Đã đủ chưa?"
# ══════════════════════════════════════════════════════════════════════════════

def check_anchor(file_target: str, muc_tieu: str, expected_items: list = None) -> dict:
    """
    Neo kiểm tra cuối phiên Flash:
    1. FILE TARGET syntax OK?
    2. Nếu có expected_items: các hàm/key mới đã tồn tại trong file?
    3. FILE XUNG QUANH vẫn OK? (import chain không gãy)
    4. PHẠM VI: chỉ file target bị sửa? (git diff check)
    
    Returns dict với "anchor_status": "GREEN" | "YELLOW" | "RED"
    """
    target_path = BASE_DIR / file_target
    result = {
        "file_target": file_target,
        "muc_tieu": muc_tieu,
        "checks": {},
        "anchor_status": "GREEN",
        "message": "",
    }
    
    # CHECK 1: Syntax OK
    try:
        with open(target_path, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        result["checks"]["syntax"] = "✅ OK"
    except SyntaxError as e:
        result["checks"]["syntax"] = f"❌ FAIL: {e}"
        result["anchor_status"] = "RED"
        result["message"] = "File bị lỗi cú pháp — KHÔNG ĐƯỢC bàn giao!"
        return result
    
    # CHECK 2: Expected items tồn tại
    if expected_items:
        content = target_path.read_text(encoding='utf-8')
        missing = []
        found = []
        for item in expected_items:
            if item in content:
                found.append(item)
            else:
                missing.append(item)
        
        result["checks"]["expected_items"] = {
            "found": found,
            "missing": missing,
        }
        if missing:
            result["anchor_status"] = "YELLOW"
            result["message"] = f"Thiếu {len(missing)} items: {missing}"
    
    # CHECK 3: Láng giềng vẫn OK
    neighbors = _find_importers(file_target)
    neighbor_status = []
    for n in neighbors:
        n_path = BASE_DIR / n["file"]
        try:
            with open(n_path, 'r', encoding='utf-8') as f:
                ast.parse(f.read())
            neighbor_status.append({"file": n["file"], "status": "✅ OK"})
        except SyntaxError as e:
            neighbor_status.append({"file": n["file"], "status": f"❌ BROKEN: {e}"})
            result["anchor_status"] = "RED"
            result["message"] = f"File láng giềng bị phá: {n['file']}"
    
    result["checks"]["neighbors"] = neighbor_status
    
    # CHECK 4: Git diff scope (nếu có git)
    try:
        import subprocess
        diff = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=str(BASE_DIR)
        )
        changed_files = [f.strip() for f in diff.stdout.strip().split('\n') if f.strip()]
        
        # Chỉ coi là "ngoài phạm vi" nếu file sửa KHÔNG phải target và KHÔNG phải agentic/
        out_of_scope = [
            f for f in changed_files 
            if f != file_target 
            and not f.startswith("agentic/") 
            and not f.startswith(".opus/")
            and not f.startswith(".agents/")
        ]
        
        result["checks"]["scope"] = {
            "files_changed": changed_files,
            "out_of_scope": out_of_scope,
        }
        if out_of_scope:
            result["anchor_status"] = "YELLOW" if result["anchor_status"] != "RED" else "RED"
            result["message"] += f" | File ngoài phạm vi bị sửa: {out_of_scope}"
    except Exception:
        result["checks"]["scope"] = {"note": "Git không khả dụng"}
    
    # Final message
    if result["anchor_status"] == "GREEN":
        result["message"] = "✅ NEO XANH — Đã đủ phần của mình. BÀN GIAO AN TOÀN."
    
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 3. TASK GRAPH — "Biết vị trí của mình trong tổng thể"
# ══════════════════════════════════════════════════════════════════════════════

def generate_task_graph(file_target: str) -> str:
    """
    Tạo bản đồ tối giản cho Flash biết:
    - Mình đang ở đâu trong hệ thống
    - File mình sửa ảnh hưởng ai
    - File nào ảnh hưởng đến mình
    
    Output: text thuần, không cần render.
    """
    context = load_bounded_context(file_target)
    
    lines = []
    lines.append(f"📍 TASK GRAPH cho: {file_target}")
    lines.append(f"   Tổng: {context['structure'].get('total_functions', '?')} hàm, "
                 f"{context['structure'].get('total_lines', '?')} dòng")
    lines.append("")
    
    # Upstream: file target import ai?
    imports = context['structure'].get('imports', [])
    if imports:
        lines.append("⬆️  FILE NÀY IMPORT:")
        for imp in imports[:10]:
            lines.append(f"    └─ {imp}")
        lines.append("")
    
    # Downstream: ai import file target?
    neighbors = context.get('neighbors', [])
    if neighbors:
        lines.append("⬇️  AI IMPORT FILE NÀY:")
        for n in neighbors:
            lines.append(f"    └─ {n['file']} (dòng {n['line']}): {n['import_statement']}")
        lines.append("")
    
    # Constraints: hàm nào đang bị dùng
    constraints = context.get('constraints', [])
    if constraints:
        lines.append("🔒 RÀNG BUỘC (KHÔNG đổi signature):")
        for c in constraints:
            lines.append(f"    └─ {c['function']}() ← dùng bởi {c['used_in']}")
        lines.append("")
    
    lines.append("─" * 50)
    lines.append("⚠️  CHỈ SỬA NỘI DUNG BÊN TRONG FILE TARGET.")
    lines.append("⚠️  KHÔNG ĐỔI TÊN HÀM ĐÃ ĐƯỢC FILE KHÁC DÙNG.")
    lines.append("⚠️  XONG VIỆC → CHẠY: python3 agentic/task_anchor.py check <file> <mục tiêu>")
    
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Cách dùng:")
        print('  python3 agentic/task_anchor.py load "tools/A04_BRAIN_HELPER.py"')
        print('  python3 agentic/task_anchor.py check "tools/A04_BRAIN_HELPER.py" "Thêm 6 hàm"')
        print('  python3 agentic/task_anchor.py graph "tools/A04_BRAIN_HELPER.py"')
        sys.exit(0)
    
    cmd = sys.argv[1]
    file_target = sys.argv[2]
    
    if cmd == "load":
        ctx = load_bounded_context(file_target)
        print(json.dumps(ctx, indent=2, ensure_ascii=False, default=str))
    
    elif cmd == "check":
        muc_tieu = sys.argv[3] if len(sys.argv) > 3 else "Kiểm tra tổng quát"
        expected = sys.argv[4].split(",") if len(sys.argv) > 4 else None
        result = check_anchor(file_target, muc_tieu, expected)
        
        # In kết quả đẹp
        status = result["anchor_status"]
        icon = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}.get(status, "⚪")
        print(f"\n{icon} ANCHOR STATUS: {status}")
        print(f"📋 Mục tiêu: {result['muc_tieu']}")
        print(f"📁 File: {result['file_target']}")
        print(f"💬 {result['message']}")
        
        for check_name, check_val in result["checks"].items():
            if isinstance(check_val, str):
                print(f"   {check_name}: {check_val}")
            elif isinstance(check_val, list):
                for item in check_val:
                    if isinstance(item, dict):
                        print(f"   {check_name}: {item.get('file', '')} → {item.get('status', '')}")
            elif isinstance(check_val, dict):
                if "missing" in check_val and check_val["missing"]:
                    print(f"   {check_name}: ❌ Thiếu: {check_val['missing']}")
                elif "found" in check_val:
                    print(f"   {check_name}: ✅ Đủ {len(check_val.get('found', []))} items")
        
        print()
        if status == "GREEN":
            print("✅ An toàn để bàn giao. DỪNG PHIÊN.")
        elif status == "YELLOW":
            print("⚠️ Cần xem lại trước khi bàn giao.")
        else:
            print("🚨 KHÔNG ĐƯỢC bàn giao. Sửa lỗi trước!")
    
    elif cmd == "graph":
        print(generate_task_graph(file_target))
    
    else:
        print(f"Lệnh không hợp lệ: {cmd}")
