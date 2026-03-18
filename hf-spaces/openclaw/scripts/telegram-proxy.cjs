/**
 * Telegram API proxy preload script for HF Spaces.
 *
 * HF Spaces blocks DNS for api.telegram.org. This script intercepts
 * globalThis.fetch() calls to fix Telegram connectivity.
 *
 * Strategy (in priority order):
 * 1. If TELEGRAM_API_ROOT is set → redirect to that mirror
 * 2. If /tmp/dns-resolved.json has an IP → rewrite URL to IP + Host header
 * 3. Otherwise → pass through (hope /etc/hosts was written successfully)
 *
 * This is needed because Node 22's built-in fetch (undici) bypasses
 * dns.lookup monkey-patching done by dns-fix.cjs.
 *
 * Adapted from democra-ai/HuggingClaw.
 * Loaded via: NODE_OPTIONS="--require /app/scripts/telegram-proxy.cjs"
 */
"use strict";

const fs = require("fs");

const TELEGRAM_API_ROOT = process.env.TELEGRAM_API_ROOT;
const OFFICIAL = "https://api.telegram.org/";
const OFFICIAL_HOST = "api.telegram.org";

// Load DoH-resolved IP if available
let resolvedIp = null;
try {
  const raw = fs.readFileSync("/tmp/dns-resolved.json", "utf8");
  const data = JSON.parse(raw);
  if (data[OFFICIAL_HOST]) {
    resolvedIp = data[OFFICIAL_HOST];
    console.log(`[telegram-proxy] DoH resolved IP for ${OFFICIAL_HOST}: ${resolvedIp}`);
  }
} catch {
  // File not ready yet — will rely on /etc/hosts or mirror
}

// Determine redirect target
let mirror = null;
let mirrorHost = null;
let mode = "passthrough";

if (TELEGRAM_API_ROOT && TELEGRAM_API_ROOT.replace(/\/+$/, "") !== "https://api.telegram.org") {
  mirror = TELEGRAM_API_ROOT.replace(/\/+$/, "") + "/";
  mirrorHost = (() => {
    try { return new URL(mirror).hostname; } catch { return mirror; }
  })();
  mode = "mirror";
} else if (resolvedIp) {
  mirror = `https://${resolvedIp}/`;
  mirrorHost = resolvedIp;
  mode = "ip-rewrite";
}

if (mode !== "passthrough") {
  const originalFetch = globalThis.fetch;
  let logged = false;

  globalThis.fetch = function patchedFetch(input, init) {
    let url;
    if (typeof input === "string") {
      url = input;
    } else if (input instanceof URL) {
      url = input.toString();
    } else if (input && typeof input === "object" && input.url) {
      url = input.url;
    }

    if (url && url.startsWith(OFFICIAL)) {
      const newUrl = mirror + url.slice(OFFICIAL.length);
      if (!logged) {
        console.log(`[telegram-proxy] Redirecting ${OFFICIAL_HOST} → ${mirrorHost} (${mode})`);
        logged = true;
      }

      // For IP-rewrite mode, add Host header so TLS SNI works
      const extraHeaders = mode === "ip-rewrite"
        ? { Host: OFFICIAL_HOST }
        : {};

      if (typeof input === "string") {
        const mergedInit = { ...init, headers: { ...extraHeaders, ...(init?.headers || {}) } };
        return originalFetch.call(this, newUrl, mergedInit);
      }
      if (input instanceof Request) {
        const newReq = new Request(newUrl, input);
        Object.entries(extraHeaders).forEach(([k, v]) => newReq.headers.set(k, v));
        return originalFetch.call(this, newReq, init);
      }
      return originalFetch.call(this, newUrl, { ...init, headers: { ...extraHeaders, ...(init?.headers || {}) } });
    }

    return originalFetch.call(this, input, init);
  };

  console.log(`[telegram-proxy] Active (mode=${mode}): ${OFFICIAL_HOST} → ${mirrorHost}`);
} else {
  console.log("[telegram-proxy] Passthrough mode — relying on /etc/hosts or system DNS");
}
