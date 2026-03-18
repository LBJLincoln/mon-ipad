#!/usr/bin/env python3
"""
DNS-over-HTTPS resolver for HF Spaces.

HF Spaces containers cannot resolve certain domains (e.g. api.telegram.org)
via the default DNS resolver. This script resolves key domains using
Cloudflare/Google DoH and writes results to a JSON file + /etc/hosts.

Adapted from democra-ai/HuggingClaw.

Usage: python3 dns-resolve.py [output-file]
"""

import json
import ssl
import sys
import urllib.request

DOH_ENDPOINTS = [
    "https://1.1.1.1/dns-query",         # Cloudflare
    "https://8.8.8.8/resolve",            # Google
    "https://dns.google/resolve",         # Google (hostname)
]

DOMAINS = [
    "api.telegram.org",
]


def resolve_via_doh(domain, endpoint, timeout=10):
    """Resolve a domain via DNS-over-HTTPS, return list of IPv4 addresses."""
    url = f"{endpoint}?name={domain}&type=A"
    req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
    ctx = ssl.create_default_context()
    resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    data = json.loads(resp.read().decode())
    return [a["data"] for a in data.get("Answer", []) if a.get("type") == 1]


def resolve_domain(domain):
    """Try multiple DoH endpoints until one succeeds."""
    for endpoint in DOH_ENDPOINTS:
        try:
            ips = resolve_via_doh(domain, endpoint)
            if ips:
                return ips
        except Exception:
            continue
    return []


def main():
    output_file = sys.argv[1] if len(sys.argv) > 1 else "/tmp/dns-resolved.json"

    # Check if system DNS works
    try:
        import socket
        socket.getaddrinfo("api.telegram.org", 443, socket.AF_INET)
        print("[dns] System DNS works for Telegram — DoH not needed")
        with open(output_file, "w") as f:
            json.dump({}, f)
        return
    except (socket.gaierror, OSError) as e:
        print(f"[dns] System DNS failed ({e}) — using DoH fallback")

    results = {}
    for domain in DOMAINS:
        ips = resolve_domain(domain)
        if ips:
            results[domain] = ips[0]
            print(f"[dns] {domain} -> {ips[0]}")
        else:
            print(f"[dns] WARNING: could not resolve {domain}")

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    # Write to /etc/hosts so undici/fetch (which bypasses dns.lookup) works
    if results:
        try:
            with open("/etc/hosts", "a") as f:
                f.write("\n# === OpenClaw DoH resolved domains ===\n")
                for domain, ip in results.items():
                    f.write(f"{ip} {domain}\n")
            print(f"[dns] Wrote {len(results)} entries to /etc/hosts")
        except PermissionError:
            print("[dns] WARNING: cannot write /etc/hosts (permission denied)")

    print(f"[dns] Resolved {len(results)}/{len(DOMAINS)} domains -> {output_file}")


if __name__ == "__main__":
    main()
