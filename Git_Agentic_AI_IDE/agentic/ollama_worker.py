"""
DNA Header v16.7 - Sovereign Purity
Role: OLLAMA_WORKER (Công nhân song song — chạy terminal riêng)
Layer: 6 (Internal Team Agentic AI)

Ollama Worker — Cho phép Team (Opus/Flash/Gemi Hi) giao task cho
LLM local (Ollama) hoặc Cloud (Groq/Cerebras) chạy SONG SONG.

3 backend:
  - LOCAL:  Ollama (qwen3.5:9b, nemotron-mini)
  - GROQ:   Groq Cloud (qwen-3-32b)
  - CEREBRAS: Cerebras Cloud (qwen-3-235b)

Cach dung:
  # Giao task cho worker local:
  python3 agentic/ollama_worker.py run "Viết hàm tính KAR" --model qwen3.5:9b

  # Giao task tu Flash Brief:
  python3 agentic/ollama_worker.py brief .opus/briefs/xxx.md

  # Giao task cho Cloud:
  python3 agentic/ollama_worker.py run "Phân tích code" --backend groq

  # Xem kết quả:
  python3 agentic/ollama_worker.py status

  # Supervisor giam sat tat ca:
  python3 agentic/ollama_worker.py monitor
"""

import json
import os
import sys
import time
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / ".opus" / "worker_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG — 3 Backend
# ══════════════════════════════════════════════════════════════════════════════

BACKENDS = {
    "local": {
        "type": "ollama",
        "base_url": "http://localhost:11434",
        "default_model": "nemotron-mini",
        "models": ["nemotron-mini", "qwen3.5:9b"],
    },
    "groq": {
        "type": "openai_compatible",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "qwen-qwq-32b",
        "env_key_pattern": "GROQ_API_KEY_",
    },
    "cerebras": {
        "type": "openai_compatible",
        "base_url": "https://api.cerebras.ai/v1",
        "default_model": "qwen-3-235b",
        "env_key_pattern": "CEREBRAS_API_KEY_",
    },
}


def _load_all_api_keys(pattern: str) -> list:
    """Load ALL API keys tu .env hoac config/.env."""
    env_files = [BASE_DIR / ".env", BASE_DIR / "config" / ".env"]
    keys = []
    seen = set()
    for env_file in env_files:
        if not env_file.exists():
            continue
        for line in env_file.read_text().splitlines():
            if line.startswith(pattern) and "=" in line:
                key = line.split("=", 1)[1].strip()
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
    return keys


def _load_api_key(pattern: str) -> Optional[str]:
    """Load API key tu .env hoac config/.env (round-robin)."""
    keys = _load_all_api_keys(pattern)
    if not keys:
        return None
    # Round-robin: hash phut hien tai de chon key
    idx = int(time.time() / 60) % len(keys)
    return keys[idx]


# ══════════════════════════════════════════════════════════════════════════════
# LLM CALL — Unified
# ══════════════════════════════════════════════════════════════════════════════

def _build_system_prompt() -> str:
    """Tao system prompt tu codebook + owner_profile."""
    parts = ["Ban la Worker trong Team Agentic AI. Lam dung yeu cau, tra loi bang tieng Viet."]
    
    # Load owner profile
    profile_path = BASE_DIR / ".opus" / "owner_profile.json"
    if profile_path.exists():
        try:
            p = json.loads(profile_path.read_text(encoding='utf-8'))
            comm = p.get("communication", {})
            parts.append(f"Owner style: {comm.get('style', 'ngan gon')}")
            prefs = p.get("preferences", {})
            if prefs.get("dislikes"):
                parts.append(f"KHONG: {', '.join(prefs['dislikes'][:3])}")
        except Exception:
            pass
    
    return "\n".join(parts)


def call_ollama(prompt: str, model: str = "qwen3.5:9b",
                system: str = None, timeout: int = 120) -> dict:
    """Goi Ollama local API."""
    import urllib.request
    import re as _re
    
    if system is None:
        system = _build_system_prompt()
    
    # Qwen3.5 can tắt thinking mode de tra loi truc tiep
    user_content = prompt
    if "qwen" in model.lower():
        user_content = "/no_think\n" + prompt
    
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 2048},
    }).encode('utf-8')
    
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            content = data.get("message", {}).get("content", "")
            # Strip <think>...</think> tags neu con sot
            content = _re.sub(r'<think>.*?</think>', '', content, flags=_re.DOTALL).strip()
            return {
                "status": "ok",
                "content": content,
                "model": model,
                "backend": "local",
                "eval_count": data.get("eval_count", 0),
                "total_duration": data.get("total_duration", 0),
            }
    except Exception as e:
        return {"status": "error", "error": str(e), "backend": "local"}


def call_cloud(prompt: str, backend: str = "groq",
               model: str = None, system: str = None,
               timeout: int = 60) -> dict:
    """Goi Cloud API (Groq/Cerebras) — OpenAI compatible.
    Tu dong thu tat ca API keys neu gap 403/429."""
    import urllib.request
    
    cfg = BACKENDS.get(backend)
    if not cfg:
        return {"status": "error", "error": f"Backend '{backend}' khong ton tai"}
    
    all_keys = _load_all_api_keys(cfg["env_key_pattern"])
    if not all_keys:
        return {"status": "error", "error": f"Khong tim thay API key cho {backend}"}
    
    if model is None:
        model = cfg["default_model"]
    if system is None:
        system = _build_system_prompt()
    
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2048,
    }).encode('utf-8')
    
    last_error = None
    for key_idx, api_key in enumerate(all_keys):
        req = urllib.request.Request(
            f"{cfg['base_url']}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                choice = data.get("choices", [{}])[0]
                usage = data.get("usage", {})
                return {
                    "status": "ok",
                    "content": choice.get("message", {}).get("content", ""),
                    "model": model,
                    "backend": backend,
                    "tokens_used": usage.get("total_tokens", 0),
                    "key_index": key_idx + 1,
                }
        except urllib.error.HTTPError as e:
            last_error = f"Key#{key_idx+1}: HTTP {e.code}"
            if e.code in (403, 429):
                continue  # Thu key tiep theo
            return {"status": "error", "error": last_error, "backend": backend}
        except Exception as e:
            return {"status": "error", "error": str(e), "backend": backend}
    
    return {"status": "error", "error": f"Tat ca {len(all_keys)} keys deu that bai. Last: {last_error}", "backend": backend}


def call_llm(prompt: str, backend: str = "local",
             model: str = None, system: str = None) -> dict:
    """Unified LLM call — chon backend tu dong."""
    if backend == "local":
        return call_ollama(prompt, model=model or "nemotron-mini", system=system)
    else:
        return call_cloud(prompt, backend=backend, model=model, system=system)


# ══════════════════════════════════════════════════════════════════════════════
# TASK EXECUTION — Doc brief, chay task, luu output
# ══════════════════════════════════════════════════════════════════════════════

def _gen_task_id(task: str) -> str:
    """Tao ID ngan gon tu noi dung task."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    h = hashlib.md5(task.encode()).hexdigest()[:6]
    return f"worker_{ts}_{h}"


def run_task(prompt: str, backend: str = "local",
             model: str = None, brief_path: str = None) -> str:
    """Chay 1 task, luu ket qua vao .opus/worker_output/."""
    task_id = _gen_task_id(prompt)
    
    print(f"🔧 Worker [{backend}] | Model: {model or 'default'}")
    print(f"📋 Task: {prompt[:80]}...")
    print(f"⏳ Dang xu ly...")
    
    start = time.time()
    result = call_llm(prompt, backend=backend, model=model)
    elapsed = round(time.time() - start, 1)
    
    # Build output report
    report = {
        "task_id": task_id,
        "ts": datetime.now().isoformat(),
        "prompt": prompt,
        "backend": backend,
        "model": result.get("model", "?"),
        "status": result.get("status", "error"),
        "elapsed_seconds": elapsed,
        "content": result.get("content", ""),
        "error": result.get("error"),
        "brief_source": brief_path,
    }
    
    # Save output
    output_path = OUTPUT_DIR / f"{task_id}.json"
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )
    
    # Print result
    if result["status"] == "ok":
        print(f"✅ Xong ({elapsed}s) | Output: {output_path.name}")
        print(f"─" * 50)
        content = result.get("content", "")
        # In toi da 1500 ky tu
        if len(content) > 1500:
            print(content[:1500] + "\n... [CẮT BỚT]")
        else:
            print(content)
        print(f"─" * 50)
    else:
        print(f"❌ Loi: {result.get('error', 'Unknown')}")
    
    return str(output_path)


def run_brief(brief_path: str, backend: str = "local",
              model: str = None) -> str:
    """Doc Flash Brief file (.md) va chay task."""
    p = Path(brief_path)
    if not p.exists():
        print(f"❌ Brief khong ton tai: {brief_path}")
        return ""
    
    content = p.read_text(encoding='utf-8')
    
    # Extract muc tieu tu brief
    prompt = f"""Đọc Flash Brief sau và thực hiện đúng yêu cầu.
Trả lời bằng tiếng Việt. Output phải là code hoặc phân tích cụ thể.

--- BRIEF ---
{content}
--- HẾT ---

Thực hiện ngay. Không hỏi lại."""
    
    return run_task(prompt, backend=backend, model=model, brief_path=brief_path)


# ══════════════════════════════════════════════════════════════════════════════
# MONITOR — Giam sat ket qua worker
# ══════════════════════════════════════════════════════════════════════════════

def show_status():
    """Hien thi trang thai cac task worker da chay."""
    outputs = sorted(OUTPUT_DIR.glob("worker_*.json"),
                     key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not outputs:
        print("📭 Chua co task nao.")
        return
    
    print(f"📋 Tong: {len(outputs)} task(s)\n")
    for f in outputs[:10]:
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            status = "✅" if data.get("status") == "ok" else "❌"
            elapsed = data.get("elapsed_seconds", "?")
            backend = data.get("backend", "?")
            prompt = data.get("prompt", "")[:60]
            print(f"  {status} [{backend}] {f.stem} ({elapsed}s)")
            print(f"     {prompt}...")
        except Exception:
            print(f"  ⚠️ {f.name} — unreadable")
    
    print(f"\n📁 Output dir: {OUTPUT_DIR}")


def read_output(task_id: str) -> Optional[dict]:
    """Doc output cua 1 task cu the."""
    # Tim file co chua task_id
    for f in OUTPUT_DIR.glob("*.json"):
        if task_id in f.name:
            return json.loads(f.read_text(encoding='utf-8'))
    return None


def monitor_loop(interval: int = 10, max_checks: int = 30):
    """Giam sat lien tuc, in ket qua moi khi co task moi."""
    print(f"👁️  SUPERVISOR MODE — Kiem tra moi {interval}s (toi da {max_checks} lan)")
    print(f"    Ctrl+C de dung.\n")
    
    seen = set(f.name for f in OUTPUT_DIR.glob("*.json"))
    
    for i in range(max_checks):
        time.sleep(interval)
        current = set(f.name for f in OUTPUT_DIR.glob("*.json"))
        new_files = current - seen
        
        if new_files:
            for fname in sorted(new_files):
                try:
                    data = json.loads((OUTPUT_DIR / fname).read_text(encoding='utf-8'))
                    status = "✅" if data.get("status") == "ok" else "❌"
                    print(f"  🆕 {status} {fname}")
                    print(f"     Backend: {data.get('backend')} | {data.get('elapsed_seconds','?')}s")
                    content = data.get("content", "")[:200]
                    if content:
                        print(f"     Preview: {content}...")
                except Exception:
                    print(f"  ⚠️ {fname} — loi doc")
            seen = current
        else:
            print(f"  ... check {i+1}/{max_checks} — chua co task moi")
    
    print("👁️  SUPERVISOR MODE ket thuc.")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def print_help():
    print("Ollama Worker — Cong nhan song song cho Team Agentic AI")
    print()
    print("Cach dung:")
    print('  python3 agentic/ollama_worker.py run "prompt" [--backend local|groq|cerebras] [--model name]')
    print('  python3 agentic/ollama_worker.py brief <path.md> [--backend local|groq|cerebras]')
    print('  python3 agentic/ollama_worker.py status')
    print('  python3 agentic/ollama_worker.py read <task_id>')
    print('  python3 agentic/ollama_worker.py monitor [--interval 10]')
    print()
    print("Backends:")
    print("  local    — Ollama (qwen3.5:9b, nemotron-mini)")
    print("  groq     — Groq Cloud (qwen-qwq-32b)")
    print("  cerebras — Cerebras Cloud (qwen-3-235b)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    # Parse optional flags
    backend = "local"
    model = None
    for i, arg in enumerate(sys.argv):
        if arg == "--backend" and i + 1 < len(sys.argv):
            backend = sys.argv[i + 1]
        if arg == "--model" and i + 1 < len(sys.argv):
            model = sys.argv[i + 1]
    
    if cmd == "run" and len(sys.argv) >= 3:
        prompt = sys.argv[2]
        run_task(prompt, backend=backend, model=model)
    
    elif cmd == "brief" and len(sys.argv) >= 3:
        brief_path = sys.argv[2]
        run_brief(brief_path, backend=backend, model=model)
    
    elif cmd == "status":
        show_status()
    
    elif cmd == "read" and len(sys.argv) >= 3:
        task_id = sys.argv[2]
        data = read_output(task_id)
        if data:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"❌ Khong tim thay task: {task_id}")
    
    elif cmd == "monitor":
        interval = 10
        for i, arg in enumerate(sys.argv):
            if arg == "--interval" and i + 1 < len(sys.argv):
                interval = int(sys.argv[i + 1])
        monitor_loop(interval=interval)
    
    else:
        print_help()
