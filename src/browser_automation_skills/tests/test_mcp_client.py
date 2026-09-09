import asyncio
import json
import sys
import os

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = r"d:\browser_automation_skills\.playwright-browsers"

async def main():
    proc = await asyncio.create_subprocess_exec(
        r"d:\browser_automation_skills\.venv\Scripts\python.exe",
        "-m", "browser_automation_skills.mcp_server", "--headed",
        cwd=r"d:\browser_automation_skills",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Read stderr in background
    async def read_stderr():
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            print(f"[STDERR] {line.decode().strip()}", flush=True)

    asyncio.create_task(read_stderr())

    # Send initialize request
    init_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }
    }
    proc.stdin.write((json.dumps(init_msg) + "\n").encode())
    await proc.stdin.drain()

    # Read response
    line = await asyncio.wait_for(proc.stdout.readline(), timeout=30)
    resp = json.loads(line.decode())
    print(f"\n=== Initialize Response ===")
    print(json.dumps(resp, indent=2, ensure_ascii=False))

    # Send initialized notification
    notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    proc.stdin.write((json.dumps(notif) + "\n").encode())
    await proc.stdin.drain()

    await asyncio.sleep(1)

    # Send list_tools request
    list_msg = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    proc.stdin.write((json.dumps(list_msg) + "\n").encode())
    await proc.stdin.drain()

    line = await asyncio.wait_for(proc.stdout.readline(), timeout=15)
    resp = json.loads(line.decode())
    print(f"\n=== List Tools Response ===")
    if "result" in resp and "tools" in resp["result"]:
        tools = resp["result"]["tools"]
        print(f"Total tools: {len(tools)}")
        for t in tools[:5]:
            print(f"  - {t['name']}: {t.get('description', '')[:60]}")
        if len(tools) > 5:
            print(f"  ... and {len(tools) - 5} more")
    else:
        print(json.dumps(resp, indent=2, ensure_ascii=False))

    proc.terminate()
    await proc.wait()

asyncio.run(main())
