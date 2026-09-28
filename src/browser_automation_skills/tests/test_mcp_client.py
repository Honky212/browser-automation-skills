# -*- coding: utf-8 -*-
"""MCP stdio 客户端集成测试：启动真实 server，完成 initialize + tools/list 握手。

只做握手与工具枚举，**不调用任何工具**，因此不会启动浏览器、不访问网络。
既可用 pytest 运行，也可直接当脚本执行：

    python tests/test_mcp_client.py

路径说明：不再硬编码 .venv / 工作区路径。
- 解释器：使用当前解释器 sys.executable（不论 myvenv、.venv 还是系统 Python）。
- 工作目录：从本文件位置逐级向上查找含 `config/config.yaml` 的目录，
  源码布局（src/browser_automation_skills/tests）与安装布局
  （<venv>/Lib/site-packages/browser_automation_skills/tests）都能命中，
  找不到时退化为当前工作目录。
"""
import asyncio
import json
import os
import sys
from pathlib import Path


def _find_workspace_root() -> Path:
    here = Path(__file__).resolve()
    for base in [here.parent, *here.parents, Path.cwd()]:
        if (base / "config" / "config.yaml").exists():
            return base
    return Path.cwd()


WORKSPACE = _find_workspace_root()
PYTHON_EXE = sys.executable


async def _start_server():
    return await asyncio.create_subprocess_exec(
        PYTHON_EXE, "-m", "browser_automation_skills.mcp_server", "--headed",
        cwd=str(WORKSPACE),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )


async def _read_response(proc, expected_id, timeout=60):
    """从 stdout 读 JSON-RPC 行，跳过日志/通知，返回 id 匹配的响应。"""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise TimeoutError(f"timeout waiting for response id={expected_id}")
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=remaining)
        if not line:
            raise RuntimeError("server closed stdout")
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line.decode())
        except json.JSONDecodeError:
            continue
        if msg.get("id") == expected_id:
            return msg


async def _stop_server(proc):
    if proc.returncode is not None:
        return
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=10)
    except asyncio.TimeoutError:
        proc.kill()


class TestMcpHandshake:
    """真实 stdio 握手（不调用工具，因此不启动浏览器）"""

    async def test_initialize_and_list_tools(self):
        proc = await _start_server()
        try:
            init = {
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            }
            proc.stdin.write((json.dumps(init) + "\n").encode())
            await proc.stdin.drain()
            resp = await _read_response(proc, 1)

            assert "result" in resp, f"initialize 失败: {resp}"
            caps = resp["result"].get("capabilities", {})
            assert caps.get("tools") is not None, "server 未声明 tools 能力"

            proc.stdin.write((json.dumps({"jsonrpc": "2.0",
                                          "method": "notifications/initialized"}) + "\n").encode())
            await proc.stdin.drain()

            proc.stdin.write((json.dumps({"jsonrpc": "2.0", "id": 2,
                                          "method": "tools/list", "params": {}}) + "\n").encode())
            await proc.stdin.drain()
            resp = await _read_response(proc, 2)

            tools = resp["result"]["tools"]
            names = {t["name"] for t in tools}
            assert names, "tools/list 返回空列表"
            assert {"navigate", "screenshot", "execute_batch_testcases",
                    "get_dom_snapshot", "execute_chain"} <= names

            # 产物路由参数必须出现在 schema 中（v1.5.6 新增）
            shot = next(t for t in tools if t["name"] == "screenshot")
            assert "output_dir" in shot["inputSchema"]["properties"]
            batch = next(t for t in tools if t["name"] == "execute_batch_testcases")
            assert "artifact_root" in batch["inputSchema"]["properties"]
        finally:
            await _stop_server(proc)


async def _main() -> int:
    """脚本模式：打印握手结果，便于人工排查。"""
    print(f"[workspace] {WORKSPACE}")
    print(f"[python]    {PYTHON_EXE}")
    proc = await _start_server()
    try:
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "test-client", "version": "1.0.0"}}}
        proc.stdin.write((json.dumps(init) + "\n").encode())
        await proc.stdin.drain()
        resp = await _read_response(proc, 1)
        print("=== Initialize Response ===")
        print(json.dumps(resp, indent=2, ensure_ascii=False)[:800])

        proc.stdin.write((json.dumps({"jsonrpc": "2.0",
                                      "method": "notifications/initialized"}) + "\n").encode())
        await proc.stdin.drain()
        await asyncio.sleep(1)

        proc.stdin.write((json.dumps({"jsonrpc": "2.0", "id": 2,
                                      "method": "tools/list", "params": {}}) + "\n").encode())
        await proc.stdin.drain()
        resp = await _read_response(proc, 2)
        tools = resp.get("result", {}).get("tools", [])
        print(f"\n=== List Tools Response ===\nTotal tools: {len(tools)}")
        for t in tools[:5]:
            print(f"  - {t['name']}: {t.get('description', '')[:60]}")
        if len(tools) > 5:
            print(f"  ... and {len(tools) - 5} more")
        return 0 if tools else 1
    finally:
        await _stop_server(proc)


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))

