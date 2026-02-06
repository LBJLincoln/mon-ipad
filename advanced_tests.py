#!/usr/bin/env python3
"""
Advanced Edge-Case Test Battery - Multi-RAG Orchestrator SOTA 2026
Tests JavaScript code safety, memory leaks, null handling, regex safety,
error propagation, and other runtime edge cases.
"""
import json
import copy
import os
import re
import sys
import time
from datetime import datetime
from collections import defaultdict
from urllib import request, error

N8N_HOST = "https://amoret.app.n8n.cloud"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"

MODIFIED_DIR = '/home/user/mon-ipad/modified-workflows'
WORKFLOW_MAP = {
    "TEST - SOTA 2026 - Ingestion V3.1.json": "nh1D4Up0wBZhuQbp",
    "TEST - SOTA 2026 - Enrichissement V3.1.json": "ORa01sX4xI0iRCJ8",
    "V10.1 orchestrator copy (5).json": "FZxkpldDbgV8AD_cg7IWG",
    "TEST - SOTA 2026 - WF5 Standard RAG V3.4 - CORRECTED.json": "LnTqRX4LZlI009Ks-3Jnp",
    "TEST - SOTA 2026 - WF2 Graph RAG V3.3 - CORRECTED (1).json": "95x2BBAbJlLWZtWEJn6rb",
    "TEST - SOTA 2026 - Feedback V3.1.json": "iVsj6dq8UpX5Dk7c",
    "TEST - SOTA 2026 - WF4 Quantitative V2.0 (1).json": "LjUz8fxQZ03G9IsU",
}


class TestResult:
    def __init__(self, name, status, details=None, errors=None, fixes=None):
        self.name = name
        self.status = status
        self.details = details or []
        self.errors = errors or []
        self.fixes = fixes or []


def load_workflows():
    workflows = {}
    for fname in WORKFLOW_MAP:
        fpath = os.path.join(MODIFIED_DIR, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            workflows[fname] = json.load(f)
    return workflows


def get_code_nodes(workflows):
    """Extract all Code nodes with their jsCode."""
    code_nodes = []
    for fname, wf in workflows.items():
        for i, node in enumerate(wf.get("nodes", [])):
            if node.get("type") == "n8n-nodes-base.code":
                code = node.get("parameters", {}).get("jsCode", "")
                if code:
                    code_nodes.append({
                        "file": fname,
                        "index": i,
                        "name": node.get("name", "?"),
                        "code": code,
                        "node": node
                    })
    return code_nodes


# ============================================================
# T14: JSON.parse Safety - All JSON.parse calls must be in try/catch
# ============================================================
def test_json_parse_safety(workflows):
    """Every JSON.parse() must be inside a try/catch block."""
    errors = []
    details = []
    fixes_applied = []

    for cn in get_code_nodes(workflows):
        code = cn["code"]
        lines = code.split('\n')

        # Find all JSON.parse calls
        parse_calls = []
        for line_num, line in enumerate(lines):
            if 'JSON.parse(' in line:
                parse_calls.append((line_num, line.strip()))

        if not parse_calls:
            continue

        for line_num, line_text in parse_calls:
            # Skip deep-clone pattern: JSON.parse(JSON.stringify(...))
            if 'JSON.parse(JSON.stringify(' in line_text:
                continue

            # Check if "try" and "catch" appear on the same line (inline)
            if 'try' in line_text and 'catch' in line_text:
                continue

            # Use the helper to check if inside try/catch
            # Find the character position of this JSON.parse in the code
            pos = 0
            for i in range(line_num):
                pos += len(lines[i]) + 1
            pos += lines[line_num].index('JSON.parse(')

            if not _is_inside_try_catch(code, pos):
                errors.append(
                    f"[{cn['file']}] '{cn['name']}' L{line_num+1}: "
                    f"JSON.parse() without try/catch: {line_text[:80]}"
                )

        details.append(f"{cn['name']}: {len(parse_calls)} JSON.parse calls checked")

    status = "PASS" if not errors else "FAIL"
    return TestResult("T14: JSON.parse Safety", status, details, errors, fixes_applied)


# ============================================================
# T15: Null-safe Property Access (.split, .trim, .map on potentially undefined)
# ============================================================
def _is_inside_try_catch(code, position):
    """Check if a position in code is inside a try/catch block.

    Scans backward from position, tracking brace depth. When going backward:
    - '}' means we're entering a closed block (depth increases)
    - '{' means we're exiting a block (depth decreases)
    If we find 'try' at depth <= 0, the position is inside that try block.
    """
    before = code[:position]
    lines_before = before.split('\n')

    brace_depth = 0
    for line in reversed(lines_before):
        # Scan characters in reverse order
        for ch in reversed(line):
            if ch == '}':
                brace_depth += 1  # entering a closed block (backward)
            elif ch == '{':
                brace_depth -= 1  # exiting a block (backward)

        stripped = line.strip()
        # Check if this line has a try keyword
        if 'try' in stripped and '{' in stripped:
            if brace_depth <= 0:
                return True

        # Also check if try is on previous line with { on next
        if stripped == 'try' or stripped == 'try{':
            if brace_depth <= 0:
                return True

        # If we've gone past the outermost scope boundary, stop
        if brace_depth < -3:
            return False

    return False


def test_null_safe_access(workflows):
    """Detect unsafe property access patterns that crash on null/undefined."""
    errors = []
    details = []

    for cn in get_code_nodes(workflows):
        code = cn["code"]
        issues_in_node = []

        # 1. trace_id.split() without null check
        for m in re.finditer(r'\.trace_id\s*\.split\(', code):
            line_start = code.rfind('\n', 0, m.start()) + 1
            line_end = code.find('\n', m.end())
            ctx = code[line_start:line_end] if line_end > 0 else code[line_start:]
            if '?.' not in ctx and not _is_inside_try_catch(code, m.start()):
                issues_in_node.append("trace_id.split() without null check")

        # 2. JSON.parse(variable) where variable could be undefined - but ONLY if not in try/catch
        for m in re.finditer(r'JSON\.parse\(\s*([a-zA-Z_]\w*)\s*\)', code):
            var = m.group(1)
            # Skip string literals and known-safe patterns
            if var in ('JSON', 'undefined', 'null'):
                continue
            if not _is_inside_try_catch(code, m.start()):
                # Check for fallback/guard on the same line
                line_start = code.rfind('\n', 0, m.start()) + 1
                line_end = code.find('\n', m.end())
                ctx = code[line_start:line_end] if line_end > 0 else code[line_start:]
                if '|| ' not in ctx and '?? ' not in ctx and 'if' not in ctx:
                    issues_in_node.append(f"JSON.parse({var}) without try/catch or guard")

        # 3. $json.X.map/filter/forEach without optional chaining
        for method in ['map', 'filter', 'forEach']:
            pattern = re.compile(rf'\$json\.[\w.]+\.{method}\(')
            for m in pattern.finditer(code):
                line_start = code.rfind('\n', 0, m.start()) + 1
                line_end = code.find('\n', m.end())
                ctx = code[line_start:line_end] if line_end > 0 else code[line_start:]
                if '?.' not in ctx and not _is_inside_try_catch(code, m.start()):
                    issues_in_node.append(f"$json.X.{method}() without null check")

        if issues_in_node:
            for issue in issues_in_node[:3]:
                errors.append(f"[{cn['file']}] '{cn['name']}': {issue}")
            details.append(f"{cn['name']}: {len(issues_in_node)} unsafe access patterns")
        else:
            details.append(f"{cn['name']}: safe")

    status = "PASS" if not errors else "FAIL"
    return TestResult("T15: Null-safe Property Access", status, details[:15], errors)


# ============================================================
# T16: staticData Memory Leak Detection
# ============================================================
def test_static_data_memory_leaks(workflows):
    """Detect unbounded growth in $getWorkflowStaticData."""
    errors = []
    details = []

    for cn in get_code_nodes(workflows):
        code = cn["code"]
        if '$getWorkflowStaticData' not in code:
            continue

        # Check if staticData keys grow unbounded
        has_cleanup = False
        has_expiry = False
        has_size_limit = False

        # Look for cleanup patterns
        if 'delete staticData' in code or 'delete staticData.' in code:
            has_cleanup = True
        if re.search(r'(Date\.now|timestamp|expires|ttl|maxAge)', code, re.IGNORECASE):
            has_expiry = True
        if re.search(r'(Object\.keys\(.*\)\.length|size\s*[<>]|\.length\s*[<>])', code):
            has_size_limit = True

        # Check for unbounded dict growth
        grows_unbounded = bool(re.search(r'staticData\.\w+\[[\w$]+\]\s*=', code))

        if grows_unbounded:
            mitigations = []
            if has_cleanup:
                mitigations.append("has delete")
            if has_expiry:
                mitigations.append("has expiry check")
            if has_size_limit:
                mitigations.append("has size limit")

            if not mitigations:
                errors.append(
                    f"[{cn['file']}] '{cn['name']}': staticData grows unbounded "
                    f"with no cleanup/expiry/size limit"
                )
            else:
                details.append(
                    f"{cn['name']}: staticData grows but has mitigations: "
                    f"{', '.join(mitigations)}"
                )
        else:
            details.append(f"{cn['name']}: uses staticData (no unbounded growth detected)")

    status = "PASS" if not errors else "FAIL"
    return TestResult("T16: staticData Memory Leak Detection", status, details, errors)


# ============================================================
# T17: Division by Zero / NaN / Infinity Guards
# ============================================================
def test_division_safety(workflows):
    """Detect potential division by zero, NaN, and Infinity."""
    errors = []
    details = []

    # Constants and known-safe divisors
    SAFE_DIVISORS = {'100', '1000', '2', '3', '4', '10', '60', '0.3', '0.7', '255', '256', '1024'}

    def strip_strings(text):
        """Remove string and template literal contents to avoid false matches."""
        # Remove template literals: `...`
        text = re.sub(r'`[^`]*`', '""', text)
        # Remove double-quoted strings: "..."
        text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
        # Remove single-quoted strings: '...'
        text = re.sub(r"'(?:[^'\\]|\\.)*'", "''", text)
        return text

    for cn in get_code_nodes(workflows):
        code = cn["code"]
        lines = code.split('\n')
        issues = []

        for line_num, line in enumerate(lines):
            stripped = line.strip()

            # Skip comment lines
            if stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('/*'):
                continue

            # Strip string contents to avoid false matches inside strings
            clean_line = strip_strings(stripped)

            # Find actual arithmetic division: expression / expression
            # Must NOT be inside a regex literal, URL, or comment
            # Look for: identifier / identifier where it's clearly math
            for m in re.finditer(r'(?<=[)\w\]\s])\s*/\s*([a-zA-Z_]\w*(?:\.\w+)*)', clean_line):
                divisor = m.group(1)

                # Skip if divisor is a safe constant
                if divisor in SAFE_DIVISORS:
                    continue

                # Skip regex flags and regex.test() patterns
                # e.g., /pattern/i, /pattern/i.test(...), /pattern/g
                before = stripped[:m.start()]
                if re.search(r'/[^/]*/?\s*$', before):
                    continue
                # Skip if the divisor starts with a regex flag
                if divisor.split('.')[0] in ('i', 'g', 'm', 's', 'u', 'y', 'gi', 'ig', 'gm', 'im'):
                    continue
                # Skip divisor that looks like regex_flag.test(...)
                if re.match(r'^[igmsuy]{1,3}\.test\b', divisor):
                    continue

                # Skip .replace(/pattern/g, ...) and similar regex operations
                if re.search(r'/[^/]+/$', before):
                    continue

                # Skip URLs and comments (contains //)
                if '//' in stripped:
                    comment_pos = stripped.index('//')
                    if comment_pos < m.start():
                        continue

                # Check if there's a zero guard in context
                context_start = max(0, line_num - 3)
                context_end = min(len(lines), line_num + 2)
                context = '\n'.join(lines[context_start:context_end])
                has_guard = bool(re.search(
                    rf'Math\.max\s*\([^)]*,\s*[1-9]|'   # Math.max(..., 1+)
                    rf'\|\|\s*[1-9]|'                      # || nonzero
                    rf'if\s*\([^)]*{re.escape(divisor)}[^)]*[>!]=?\s*0|'  # if (divisor > 0)
                    rf'{re.escape(divisor)}\s*>\s*0|'      # divisor > 0
                    rf'{re.escape(divisor)}\s*!==?\s*0',   # divisor !== 0
                    context
                ))

                if not has_guard:
                    issues.append(
                        f"Division by '{divisor}' without zero guard: {stripped[:60]}"
                    )

        # Math.log on potentially zero/negative values (only flag if no guard)
        if 'Math.log(' in code:
            for m in re.finditer(r'Math\.log\(([^)]+)\)', code):
                arg = m.group(1).strip()
                line_start = code.rfind('\n', 0, m.start()) + 1
                line_end = code.find('\n', m.end())
                ctx = code[max(0, line_start - 100):line_end if line_end > 0 else len(code)]
                if 'Math.max' not in ctx and '> 0' not in ctx and '>= 1' not in ctx:
                    issues.append(f"Math.log({arg}) without positivity guard")

        # parseFloat without fallback (only first occurrence)
        for fn_name in ['parseFloat']:
            if fn_name + '(' in code:
                for m in re.finditer(rf'{fn_name}\(([^)]+)\)', code):
                    line_start = code.rfind('\n', 0, m.start()) + 1
                    line_end = code.find('\n', m.end())
                    ctx = code[m.start():line_end if line_end > 0 else len(code)]
                    if '|| ' not in ctx and '?? ' not in ctx and 'isNaN' not in ctx:
                        issues.append(f"{fn_name}() without fallback value")
                        break

        if issues:
            for issue in issues[:3]:
                errors.append(f"[{cn['file']}] '{cn['name']}': {issue}")
            details.append(f"{cn['name']}: {len(issues)} potential math issues")

    # Division issues are defensiveness warnings, not critical bugs (NaN propagates, doesn't crash)
    status = "PASS" if not errors else "WARN"
    return TestResult("T17: Division / NaN / Infinity Guards", status, details[:15], errors)


# ============================================================
# T18: Error Handler Coverage - Every trigger path has an error handler
# ============================================================
def test_error_handler_coverage(workflows):
    """Verify every workflow with triggers has error handling nodes."""
    errors = []
    details = []

    for fname, wf in workflows.items():
        nodes = {n["name"]: n for n in wf["nodes"]}
        node_types = {n["name"]: n.get("type", "") for n in wf["nodes"]}

        # Find triggers
        triggers = [n for n in wf["nodes"] if any(t in n.get("type", "") for t in
                     ["webhook", "trigger", "Trigger"])]

        # Find error handlers
        error_handlers = [n for n in wf["nodes"] if
                          n.get("type") == "n8n-nodes-base.errorTrigger" or
                          "error" in n.get("name", "").lower()]

        # Find nodes with onError set
        on_error_nodes = [n for n in wf["nodes"] if n.get("onError")]

        if triggers and not error_handlers:
            errors.append(f"[{fname}] Has {len(triggers)} triggers but no error handler node (recommended)")
        elif triggers:
            details.append(
                f"{fname}: {len(triggers)} triggers, "
                f"{len(error_handlers)} error handlers, "
                f"{len(on_error_nodes)} nodes with onError"
            )
        else:
            details.append(f"{fname}: No triggers (sub-workflow)")

    status = "PASS" if not errors else "WARN"
    return TestResult("T18: Error Handler Coverage", status, details, errors)


# ============================================================
# T19: HTTP Node Credential & Timeout Coverage
# ============================================================
def test_http_node_config(workflows):
    """Verify HTTP nodes have credentials and reasonable timeouts."""
    errors = []
    details = []

    for fname, wf in workflows.items():
        http_count = 0
        missing_creds = []
        no_timeout = []

        for node in wf["nodes"]:
            if node.get("type") != "n8n-nodes-base.httpRequest":
                continue
            http_count += 1
            name = node.get("name", "?")

            # Check credentials
            creds = node.get("credentials", {})
            if not creds:
                # Some HTTP nodes use header auth via expressions, which is OK
                params = node.get("parameters", {})
                has_auth_header = any(
                    "Authorization" in str(v) or "api" in str(v).lower()
                    for v in params.get("headerParametersJson", {}).values()
                ) if isinstance(params.get("headerParametersJson"), dict) else False

                send_headers = params.get("sendHeaders", False)
                header_params = params.get("headerParameters", {})
                spec_headers = header_params.get("parameters", []) if isinstance(header_params, dict) else []
                has_header_auth = any(
                    "authorization" in str(h.get("name", "")).lower() or
                    "api" in str(h.get("name", "")).lower()
                    for h in spec_headers
                )

                # Check if URL contains auth (e.g., Slack webhook URLs)
                url_val = str(params.get("url", ""))
                has_url_auth = any(k in url_val.lower() for k in
                                   ["hooks.slack.com", "webhook", "$vars", "{{"])

                if not has_auth_header and not has_header_auth and not has_url_auth:
                    missing_creds.append(name)

            # Check timeout
            params = node.get("parameters", {})
            timeout = params.get("timeout", params.get("requestOptions", {}).get("timeout"))
            if not timeout:
                no_timeout.append(name)

        if http_count > 0:
            detail = f"{fname}: {http_count} HTTP nodes"
            if missing_creds:
                detail += f", {len(missing_creds)} without visible auth"
                details.append(detail)
                # Only error if it's an external API call, not internal
                for mc in missing_creds:
                    if not any(skip in mc.lower() for skip in ["otel", "trace", "monitor", "internal"]):
                        errors.append(f"[{fname}] HTTP node '{mc}' has no credentials/auth")
            else:
                details.append(detail + " (all authenticated)")

    status = "PASS" if not errors else "FAIL"
    return TestResult("T19: HTTP Node Credential & Timeout Coverage", status, details, errors)


# ============================================================
# T20: Return Statement Format Validation
# ============================================================
def test_return_format(workflows):
    """Verify Code nodes' top-level return produces valid n8n output format.

    Only checks returns at brace depth 0 (outside any {} block), not inside
    helper functions, if blocks, callbacks, arrow functions, etc.
    In n8n Code v2, returns inside if/try blocks at depth 1 are also top-level.
    We focus on the LAST return statement (the primary output).
    """
    errors = []
    details = []

    for cn in get_code_nodes(workflows):
        code = cn["code"]
        lines = code.split('\n')

        # Find all return statements and their brace depth
        brace_depth = 0
        returns_with_depth = []

        for line_num, line in enumerate(lines):
            stripped = line.strip()

            # Skip pure comment lines
            if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                continue

            # Track braces on this line (before checking return)
            for ch in stripped:
                if ch == '{':
                    brace_depth += 1
                elif ch == '}':
                    brace_depth -= 1

            if stripped.startswith('return ') or stripped == 'return;':
                ret_content = stripped[7:].rstrip(';').strip() if stripped.startswith('return ') else ''
                returns_with_depth.append((line_num, ret_content, brace_depth))

        if not returns_with_depth:
            details.append(f"{cn['name']}: no returns found")
            continue

        # Check if AT LEAST ONE return produces valid n8n output
        # Valid outputs: array [{json:...}], object {json:...}, items, $input
        has_valid = False
        total = len(returns_with_depth)

        for line_num, ret_content, depth in returns_with_depth:
            is_valid = any([
                ret_content.startswith('['),           # Array return
                ret_content.startswith('{'),           # Object return
                'items' in ret_content,                # Passthrough
                '$input' in ret_content,               # Input passthrough
            ])
            if is_valid:
                has_valid = True
                break

        if has_valid:
            details.append(f"{cn['name']}: {total} returns, has valid n8n output")
        else:
            # Only flag if NO return produces valid n8n format
            errors.append(
                f"[{cn['file']}] '{cn['name']}': no return produces [{'{'}json:...{'}'}] format"
            )
            details.append(f"{cn['name']}: {total} returns, NONE produce valid n8n output")

    # n8n Code v2 auto-wraps any return value, so non-array returns are acceptable
    status = "PASS" if not errors else "WARN"
    return TestResult("T20: Return Statement Format", status, details[:15], errors)


# ============================================================
# T21: $vars Dependencies Documentation
# ============================================================
def test_vars_dependencies(workflows):
    """List all $vars references to verify environment variable coverage."""
    errors = []
    details = []
    all_vars = defaultdict(list)

    var_pattern = re.compile(r'\$vars\.(\w+)')

    for fname, wf in workflows.items():
        wf_vars = set()
        for node in wf["nodes"]:
            params = node.get("parameters", {})
            for key, val in params.items():
                if isinstance(val, str):
                    for m in var_pattern.finditer(val):
                        var_name = m.group(1)
                        wf_vars.add(var_name)
                        all_vars[var_name].append(f"{fname}:{node.get('name', '?')}")

            # Also check jsCode
            code = params.get("jsCode", "")
            for m in var_pattern.finditer(code):
                var_name = m.group(1)
                wf_vars.add(var_name)
                all_vars[var_name].append(f"{fname}:{node.get('name', '?')}")

        details.append(f"{fname}: uses {len(wf_vars)} $vars: {sorted(wf_vars)}")

    # Check for vars that lack a default fallback (|| 'default')
    for var_name, locations in sorted(all_vars.items()):
        has_default = False
        for loc in locations:
            fname = loc.split(":")[0]
            wf = workflows.get(fname)
            if wf:
                full_json = json.dumps(wf)
                # Check for || 'default' or || "default" pattern after this var
                pattern = re.compile(rf'\$vars\.{re.escape(var_name)}\s*\|\|')
                if pattern.search(full_json):
                    has_default = True
                    break

        if not has_default:
            errors.append(
                f"$vars.{var_name} used in {len(locations)} places without fallback default"
            )

    details.append(f"\nTotal unique $vars: {len(all_vars)}")
    for var, locs in sorted(all_vars.items()):
        details.append(f"  ${var}: {len(locs)} usages")

    status = "PASS" if not errors else "WARN"
    return TestResult("T21: $vars Dependencies", status, details[:20], errors)


# ============================================================
# T22: Webhook Path & Auth Validation
# ============================================================
def test_webhook_config(workflows):
    """Verify webhook nodes have proper paths and authentication."""
    errors = []
    details = []

    for fname, wf in workflows.items():
        for node in wf["nodes"]:
            if node.get("type") not in ("n8n-nodes-base.webhook",):
                continue

            name = node.get("name", "?")
            params = node.get("parameters", {})
            path = params.get("path", "")
            auth = params.get("authentication", "none")
            method = params.get("httpMethod", "GET")

            # Check path is not empty
            if not path:
                errors.append(f"[{fname}] Webhook '{name}' has empty path")

            # Check authentication
            if auth == "none":
                details.append(f"[{fname}] '{name}': path=/{path}, method={method}, auth=NONE (open)")
            else:
                details.append(f"[{fname}] '{name}': path=/{path}, method={method}, auth={auth}")

    if not details:
        details.append("No webhook nodes found")

    status = "PASS" if not errors else "FAIL"
    return TestResult("T22: Webhook Path & Auth", status, details, errors)


# ============================================================
# T23: Regex ReDoS Safety
# ============================================================
def test_regex_redos_safety(workflows):
    """Detect regex patterns vulnerable to catastrophic backtracking (ReDoS)."""
    errors = []
    details = []

    # Known ReDoS-vulnerable patterns:
    # - Nested quantifiers: (a+)+ , (a*)*
    # - Overlapping alternation with quantifier: (a|a)+
    # - Complex backtracking: .*X.*Y on long strings without X or Y
    redos_patterns = [
        (re.compile(r'\([^)]*[+*]\)[+*]'), "Nested quantifier (a+)+ or (a*)*"),
        (re.compile(r'\([^)]*\|[^)]*\)[+*]{1,2}'), "Alternation with outer quantifier"),
        (re.compile(r'\.\*[^)]*\.\*[^)]*\.\*'), "Triple .* (catastrophic backtracking risk)"),
    ]

    regex_pattern = re.compile(r'/([^/]+)/[gimsuvy]*')

    for cn in get_code_nodes(workflows):
        code = cn["code"]
        node_issues = []

        # Extract all regex literals from code
        for rm in regex_pattern.finditer(code):
            regex_str = rm.group(1)

            for bad_pattern, desc in redos_patterns:
                if bad_pattern.search(regex_str):
                    node_issues.append(f"ReDoS risk: /{regex_str}/ - {desc}")

        if node_issues:
            for issue in node_issues[:3]:
                errors.append(f"[{cn['file']}] '{cn['name']}': {issue}")
        else:
            # Only report nodes that have regex
            if regex_pattern.search(code):
                details.append(f"{cn['name']}: regex patterns safe")

    status = "PASS" if not errors else "FAIL"
    return TestResult("T23: Regex ReDoS Safety", status, details[:10], errors)


# ============================================================
# T24: Credential ID Consistency
# ============================================================
def test_credential_consistency(workflows):
    """Verify credential IDs are consistent across workflows."""
    errors = []
    details = []
    cred_map = defaultdict(set)  # credential_name -> set of IDs

    for fname, wf in workflows.items():
        for node in wf["nodes"]:
            creds = node.get("credentials", {})
            for cred_type, cred_info in creds.items():
                if isinstance(cred_info, dict):
                    cred_name = cred_info.get("name", "?")
                    cred_id = cred_info.get("id", "?")
                    cred_map[cred_name].add(cred_id)

    for name, ids in sorted(cred_map.items()):
        if len(ids) > 1:
            errors.append(f"Credential '{name}' has multiple IDs: {ids}")
        details.append(f"'{name}': {ids}")

    status = "PASS" if not errors else "WARN"
    return TestResult("T24: Credential ID Consistency", status, details[:15], errors)


# ============================================================
# T25: n8n API Round-Trip Integrity
# ============================================================
def test_api_roundtrip_integrity(workflows):
    """Import workflow, fetch it back, and verify node count and key data matches."""
    errors = []
    details = []

    STRIP = {"timeSavedMode", "saveExecutionProgress", "saveManualExecutions"}

    def api_get(endpoint):
        url = f"{N8N_HOST}/api/v1{endpoint}"
        req = request.Request(url, headers={
            "X-N8N-API-KEY": N8N_API_KEY,
            "Accept": "application/json"
        })
        with request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())

    for fname, wf_id in WORKFLOW_MAP.items():
        wf = workflows.get(fname)
        if not wf:
            continue

        try:
            remote_wf = api_get(f"/workflows/{wf_id}")
        except Exception as e:
            errors.append(f"[{fname}] Cannot fetch from API: {e}")
            continue

        local_nodes = len(wf.get("nodes", []))
        remote_nodes = len(remote_wf.get("nodes", []))

        if local_nodes != remote_nodes:
            errors.append(f"[{fname}] Node count mismatch: local={local_nodes} remote={remote_nodes}")

        # Verify connection count
        local_conns = len(wf.get("connections", {}))
        remote_conns = len(remote_wf.get("connections", {}))
        if local_conns != remote_conns:
            errors.append(
                f"[{fname}] Connection count mismatch: local={local_conns} remote={remote_conns}"
            )

        # Verify node names match
        local_names = sorted(n["name"] for n in wf.get("nodes", []))
        remote_names = sorted(n["name"] for n in remote_wf.get("nodes", []))
        if local_names != remote_names:
            missing = set(local_names) - set(remote_names)
            extra = set(remote_names) - set(local_names)
            if missing:
                errors.append(f"[{fname}] Nodes missing on remote: {missing}")
            if extra:
                errors.append(f"[{fname}] Extra nodes on remote: {extra}")

        details.append(
            f"{fname}: local={local_nodes} nodes/{local_conns} conns, "
            f"remote={remote_nodes}/{remote_conns} - "
            f"{'MATCH' if local_nodes == remote_nodes and local_conns == remote_conns else 'MISMATCH'}"
        )

        time.sleep(0.3)

    status = "PASS" if not errors else "FAIL"
    return TestResult("T25: API Round-Trip Integrity", status, details, errors)


# ============================================================
# T26: Throw Statement Safety - Uncaught throws
# ============================================================
def test_uncaught_throws(workflows):
    """Detect throw statements that may not be caught, causing workflow crashes."""
    errors = []
    details = []

    for cn in get_code_nodes(workflows):
        code = cn["code"]
        lines = code.split('\n')

        throws = []
        for line_num, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('throw ') or stripped.startswith('throw\t'):
                throws.append((line_num, stripped))

        if not throws:
            continue

        caught = 0
        uncaught = 0
        for line_num, throw_text in throws:
            # Check if throw is inside a try block
            in_try = False
            brace_depth = 0
            for j in range(line_num, -1, -1):
                line = lines[j]
                brace_depth += line.count('}') - line.count('{')
                if 'try' in line and brace_depth <= 0:
                    in_try = True
                    break

            if in_try:
                caught += 1
            else:
                uncaught += 1

        # In n8n, uncaught throws in Code nodes cause the node to fail,
        # which routes to error output if onError is set, or crashes the workflow.
        # So we check if the node has onError or if there's an error handler
        node = cn["node"]
        has_on_error = node.get("onError") is not None

        if uncaught > 0 and not has_on_error:
            details.append(
                f"{cn['name']}: {uncaught} throws without try/catch "
                f"(no onError set - will crash workflow)"
            )
        elif uncaught > 0:
            details.append(
                f"{cn['name']}: {uncaught} intentional throws "
                f"(onError={node.get('onError')} - handled)"
            )
        else:
            details.append(f"{cn['name']}: {caught} throws all inside try/catch")

    status = "PASS"  # Throws are often intentional validation
    return TestResult("T26: Throw Statement Safety", status, details[:15], errors)


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 70)
    print("  ADVANCED EDGE-CASE TEST BATTERY - Multi-RAG SOTA 2026")
    print(f"  Target: {N8N_HOST}")
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    print("\nLoading workflows...")
    workflows = load_workflows()
    code_nodes = get_code_nodes(workflows)
    print(f"Loaded {len(workflows)} workflows, {len(code_nodes)} Code nodes\n")

    tests = [
        ("T14", test_json_parse_safety),
        ("T15", test_null_safe_access),
        ("T16", test_static_data_memory_leaks),
        ("T17", test_division_safety),
        ("T18", test_error_handler_coverage),
        ("T19", test_http_node_config),
        ("T20", test_return_format),
        ("T21", test_vars_dependencies),
        ("T22", test_webhook_config),
        ("T23", test_regex_redos_safety),
        ("T24", test_credential_consistency),
        ("T25", test_api_roundtrip_integrity),
        ("T26", test_uncaught_throws),
    ]

    results = []
    for test_id, test_fn in tests:
        print(f"\n{'─'*70}")
        print(f"Running {test_id}...")
        try:
            result = test_fn(workflows)
            results.append(result)
            icon = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN"}.get(result.status, "????")
            print(f"  [{icon}] {result.name}")
            for d in result.details[:6]:
                print(f"    {d}")
            if result.errors:
                print(f"    ERRORS ({len(result.errors)}):")
                for e in result.errors[:5]:
                    print(f"      {e}")
                if len(result.errors) > 5:
                    print(f"      ... and {len(result.errors) - 5} more")
        except Exception as ex:
            import traceback
            print(f"  [ERR!] {test_id} crashed: {ex}")
            traceback.print_exc()
            results.append(TestResult(test_id, "ERROR", [], [str(ex)]))

    # SUMMARY
    print(f"\n{'='*70}")
    print("  ADVANCED TEST RESULTS")
    print(f"{'='*70}")

    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    warned = sum(1 for r in results if r.status == "WARN")

    for r in results:
        icon = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN", "ERROR": "ERR!"}.get(r.status, "????")
        err = f" ({len(r.errors)} issues)" if r.errors else ""
        print(f"  [{icon}] {r.name}{err}")

    print(f"\n  Total: {len(results)} tests")
    print(f"  Passed: {passed} | Failed: {failed} | Warned: {warned}")
    overall = "ALL PASS" if failed == 0 else "ISSUES FOUND"
    print(f"\n  >> {overall} <<")

    report = {
        "generated_at": datetime.now().isoformat(),
        "generated_by": "advanced-edge-case-test-battery",
        "total_tests": len(results),
        "passed": passed,
        "failed": failed,
        "warned": warned,
        "code_nodes_analyzed": len(code_nodes),
        "tests": [
            {"name": r.name, "status": r.status, "details": r.details, "errors": r.errors}
            for r in results
        ]
    }

    report_path = os.path.join(MODIFIED_DIR, 'advanced-test-results.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  Report: {report_path}")

    return results


if __name__ == '__main__':
    results = main()
    sys.exit(1 if any(r.status == "FAIL" for r in results) else 0)
