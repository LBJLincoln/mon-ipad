#!/usr/bin/env python3
"""
Test a stdio MCP server by sending initialize + tools/list, then killing it.
Returns: JSON with {ok, name, tools_count, tools, error}
Usage: python3 test-mcp-server.py [--timeout N] <command> [args...]
"""
import subprocess
import sys
import json
import time
import selectors
import signal


INIT_MSG = json.dumps({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"}
    }
})

TOOLS_MSG = json.dumps({
    "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}
})


def test_server(cmd, timeout=20):
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        sel = selectors.DefaultSelector()
        sel.register(proc.stdout, selectors.EVENT_READ)

        lines = []
        deadline = time.time() + timeout

        # Send init message
        proc.stdin.write((INIT_MSG + "\n").encode())
        proc.stdin.flush()

        # Wait for init response (with retries for slow servers like npx)
        got_init = False
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            events = sel.select(timeout=min(remaining, 0.5))
            if events:
                data = proc.stdout.readline()
                if data:
                    line = data.decode().strip()
                    if line.startswith("{"):
                        lines.append(line)
                        try:
                            msg = json.loads(line)
                            if "serverInfo" in msg.get("result", {}):
                                got_init = True
                        except (json.JSONDecodeError, TypeError):
                            pass
                    if got_init:
                        break
                else:
                    break  # EOF

        if not got_init:
            # Try to read stderr for diagnostics
            stderr_out = ""
            try:
                proc.stdin.close()
                proc.terminate()
                _, stderr_bytes = proc.communicate(timeout=2)
                stderr_out = stderr_bytes.decode()[:300]
            except Exception:
                pass
            return {"ok": False, "error": f"no init response. stderr: {stderr_out}"}

        # Small delay then send tools/list
        time.sleep(0.3)
        proc.stdin.write((TOOLS_MSG + "\n").encode())
        proc.stdin.flush()

        # Wait for tools/list response
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            events = sel.select(timeout=min(remaining, 0.5))
            if events:
                data = proc.stdout.readline()
                if data:
                    line = data.decode().strip()
                    if line.startswith("{"):
                        lines.append(line)
                        try:
                            msg = json.loads(line)
                            if "tools" in msg.get("result", {}):
                                break  # Got tools response
                        except (json.JSONDecodeError, TypeError):
                            pass
                else:
                    break  # EOF

        sel.close()

        # Parse all collected responses
        server_name = ""
        tools = []
        for line in lines:
            try:
                msg = json.loads(line)
                result = msg.get("result", {})
                if "serverInfo" in result:
                    server_name = result["serverInfo"].get("name", "")
                if "tools" in result:
                    tools = [t["name"] for t in result["tools"]]
                if "error" in msg:
                    err = msg["error"]
                    return {"ok": False, "name": server_name,
                            "error": f"RPC error: {err.get('message', str(err))}"}
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        if tools:
            return {"ok": True, "name": server_name, "tools_count": len(tools), "tools": tools}
        elif server_name:
            return {"ok": False, "name": server_name, "tools_count": 0,
                    "error": "starts but tools/list returned nothing"}
        else:
            return {"ok": False, "error": "no usable response"}

    except FileNotFoundError:
        return {"ok": False, "error": f"command not found: {cmd[0]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        if proc and proc.poll() is None:
            try:
                proc.stdin.close()
            except Exception:
                pass
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


if __name__ == "__main__":
    args = sys.argv[1:]
    timeout = 20

    if args and args[0] == "--timeout":
        timeout = int(args[1])
        args = args[2:]

    if not args:
        print(json.dumps({"ok": False, "error": "usage: test-mcp-server.py [--timeout N] <command> [args...]"}))
        sys.exit(1)

    result = test_server(args, timeout=timeout)
    print(json.dumps(result))
    sys.exit(0 if result["ok"] else 1)
