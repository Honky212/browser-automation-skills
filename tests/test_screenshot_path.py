# -*- coding: utf-8 -*-
"""端到端测试：通过 stdio 驱动 MCP server，调 screenshot 工具，验证截图落到 ./screenshots/。

故意用 path="./probe.png"（带 ./ 前缀）——这是旧代码下会散落到 cwd（项目根）的场景。
"""
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(r"d:\browser_automation_skills")
PYTHON = str(ROOT / ".venv" / "Scripts" / "python.exe")
ENV = dict(os.environ)
ENV["PLAYWRIGHT_BROWSERS_PATH"] = str(ROOT / ".playwright-browsers")

PROBE_FILENAME = "probe.png"
PROBE_REL = f"./{PROBE_FILENAME}"        # 故意带 ./ 前缀
EXPECTED_DIR = ROOT / "screenshots"
ROOT_PROBE = ROOT / PROBE_FILENAME        # 不该出现这里
DIR_PROBE = EXPECTED_DIR / PROBE_FILENAME  # 应该出现这里


async def read_response(proc, expected_id, timeout=90):
    """从 stdout 读 JSON-RPC，跳过通知/日志，只返回 id 匹配的响应。"""
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            raise TimeoutError(f"timeout waiting for id={expected_id}")
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=remaining)
        if not line:
            raise RuntimeError("server closed stdout")
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line.decode())
        except json.JSONDecodeError:
            continue  # 跳过非 JSON 行
        if msg.get("id") == expected_id:
            return msg
        # 其余（通知、日志等）跳过


async def main():
    # 清理残留
    for p in (ROOT_PROBE, DIR_PROBE):
        if p.exists():
            p.unlink()

    print(f"[test] cwd               = {ROOT}")
    print(f"[test] 期望截图目录       = {EXPECTED_DIR}")
    print(f"[test] 调用 screenshot(path={PROBE_REL!r})")
    print()

    proc = await asyncio.create_subprocess_exec(
        PYTHON, "-m", "browser_automation_skills.mcp_server", "--headed",
        cwd=str(ROOT),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=ENV,
    )

    err_tail = []
    try:
        # 1. initialize 握手
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "screenshot-test", "version": "1.0"}}}
        proc.stdin.write((json.dumps(init) + "\n").encode())
        await proc.stdin.drain()
        resp = await read_response(proc, 1, 60)
        assert "result" in resp, f"initialize 失败: {resp}"
        caps = resp["result"].get("capabilities", {})
        print(f"[1/4] initialize OK, capabilities.tools = {caps.get('tools')}")

        # 2. notifications/initialized
        proc.stdin.write((json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n").encode())
        await proc.stdin.drain()

        # 3. 调 screenshot 工具（首次会懒加载浏览器，给 120s）
        call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "screenshot",
                           "arguments": {"path": PROBE_REL, "full_page": False}}}
        proc.stdin.write((json.dumps(call) + "\n").encode())
        await proc.stdin.drain()
        r2 = await read_response(proc, 2, 120)
        if "error" in r2:
            print(f"[2/4] tools/call 返回错误: {r2['error']}")
            return 1

        text = r2["result"]["content"][0]["text"]
        payload = json.loads(text)
        print(f"[2/4] screenshot success={payload.get('success')}")
        print(f"      message={payload.get('message')}")
        saved_path = (payload.get("data") or {}).get("path")
        print(f"      返回的保存路径={saved_path}")

        # 4. 断言
        ok_path = bool(saved_path) and os.path.normpath(saved_path).lower() == str(DIR_PROBE).lower()
        ok_file_in_dir = DIR_PROBE.exists()
        ok_not_in_root = not ROOT_PROBE.exists()
        if DIR_PROBE.exists():
            print(f"[3/4] screenshots/probe.png 存在，大小={DIR_PROBE.stat().st_size} 字节")
        else:
            print(f"[3/4] screenshots/probe.png 不存在")
        print(f"[4/4] 项目根 probe.png 散落检查: {'未散落' if ok_not_in_root else '散落到根!'}")

        print()
        print(f"  [1] 返回路径在 ./screenshots/ 下 : {'PASS' if ok_path else 'FAIL'}")
        print(f"  [2] 文件确实生成在 screenshots/   : {'PASS' if ok_file_in_dir else 'FAIL'}")
        print(f"  [3] 项目根没有散落的 probe.png     : {'PASS' if ok_not_in_root else 'FAIL'}")

        all_ok = ok_path and ok_file_in_dir and ok_not_in_root
        print()
        print(f"===== {'ALL PASS —— 截图已固定落到 ./screenshots/' if all_ok else 'FAILED'} =====")
        return 0 if all_ok else 1

    finally:
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            err = await asyncio.wait_for(proc.stderr.read(), timeout=2)
            err_text = err.decode(errors="replace")
            if err_text.strip():
                print("\n--- server stderr (末 30 行) ---")
                print("\n".join(err_text.splitlines()[-30:]))
        except Exception:
            pass


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
