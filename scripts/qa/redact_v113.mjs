import fs from 'node:fs';

const SENSITIVE_LABEL = /(?:authorization|cookie|token|secret|password|api[-_ ]?key|credential|set-cookie|header|x-api-key)\b/i;

function redactString(value, replacements = []) {
  let output = String(value);
  for (const [source, marker] of replacements) {
    if (!source) continue;
    output = output.replaceAll(source, marker);
    output = output.replaceAll(source.replaceAll('\\', '/'), marker);
    output = output.replaceAll(source.replaceAll('/', '\\'), marker);
  }
  output = output.replace(/(^|[\r\n])([^\r\n]*?\b(?:authorization|cookie|token|secret|password|api[-_ ]?key|credential|set-cookie|header|x-api-key)\b\s*[:=]\s*)[^\r\n]*/gim, '$1$2[REDACTED]');
  output = output.replace(/\b(?:[A-Za-z]:[\\/]|\\\\)[^\r\n,;"']+/g, match => /(?:Users|Documents and Settings)[\\/]/i.test(match) ? '[USER_PATH]' : match);
  output = output.replace(/[A-Za-z0-9+/_=-]{32,}/g, '[REDACTED]');
  return output;
}

function redact(value, options = {}) {
  const replacements = options.replacements ?? [];
  if (typeof value === 'string') return redactString(value, replacements);
  if (Array.isArray(value)) return value.map(item => redact(item, options));
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, SENSITIVE_LABEL.test(key) ? '[REDACTED]' : redact(child, options)]));
  return value;
}

function invalidateReceiptFiles(artifactRoot) {
  fs.rmSync(`${artifactRoot}/react-diagnostics.json`, { force: true });
  if (!fs.existsSync(artifactRoot)) return;
  for (const entry of fs.readdirSync(artifactRoot, { withFileTypes: true })) {
    if (entry.isFile() && /^react-diagnostics\.[^.]+\.[^.]+\.tmp$/.test(entry.name)) fs.rmSync(`${artifactRoot}/${entry.name}`, { force: true });
  }
}

export { redact, redactString, invalidateReceiptFiles, SENSITIVE_LABEL };
