// Strip likely-sensitive credentials from JSON-shaped strings before they
// are persisted to chat_logs. The runtime upstream key (cfg.providers[*].apiKey)
// is set as an HTTP header by callOpenAICompat, so it never appears in the
// JSON bodies we serialize here. The patterns below cover the cases where a
// user's prompt, a tool call argument, or a JSON field accidentally carries
// a secret (sk-*, Bearer xxx, "api_key": "...", etc).

const TOKEN_PLACEHOLDER = "<redacted>";

type Rule = { pattern: RegExp; replacement: string | ((match: string) => string) };

const RULES: Rule[] = [
  // JSON fields whose names look credential-ish — preserve the key + colon,
  // replace the value (with quotes) so the JSON stays valid.
  {
    pattern: /"(authorization|api[_-]?key|access[_-]?token|secret[_-]?key|bearer[_-]?token|password)"(\s*:\s*)"[^"\\]*(?:\\.[^"\\]*)*"/gi,
    replacement: (match: string) => {
      const m = match.match(/^"([^"]+)"(\s*:\s*)/);
      if (!m) return match;
      return `"${m[1]}"${m[2]}"<redacted>"`;
    },
  },
  // Bearer tokens inside string values.
  { pattern: /Bearer\s+[A-Za-z0-9._\-+/=]{10,}/g, replacement: `Bearer ${TOKEN_PLACEHOLDER}` },
  // Anthropic-style keys (must come before sk- so it matches longer prefix first).
  { pattern: /\bsk-ant-[A-Za-z0-9_\-]{16,}/g, replacement: `sk-ant-${TOKEN_PLACEHOLDER}` },
  // Provider-style secret keys: sk-..., xai-..., AIza...
  { pattern: /\bsk-[A-Za-z0-9_\-]{16,}/g, replacement: `sk-${TOKEN_PLACEHOLDER}` },
  { pattern: /\bxai-[A-Za-z0-9_\-]{16,}/g, replacement: `xai-${TOKEN_PLACEHOLDER}` },
  { pattern: /\bAIza[0-9A-Za-z_\-]{20,}/g, replacement: `AIza${TOKEN_PLACEHOLDER}` },
];

export function redactSensitive(text: string): string {
  if (!text) return text;
  let out = text;
  for (const r of RULES) {
    out = typeof r.replacement === "string"
      ? out.replace(r.pattern, r.replacement)
      : out.replace(r.pattern, r.replacement);
  }
  return out;
}
