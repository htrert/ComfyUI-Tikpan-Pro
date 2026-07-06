import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const alerts = JSON.parse(readFileSync(join(root, "alerts.json"), "utf8"));
const operators = new Set([">", ">=", "<", "<=", "==", "!="]);
const severities = new Set(["info", "warning", "critical"]);

assert(Number.isInteger(alerts.version) && alerts.version > 0, "alerts.version must be a positive integer.");
assert(Array.isArray(alerts.rules) && alerts.rules.length > 0, "alerts.rules must be a non-empty array.");

const seen = new Set();
for (const rule of alerts.rules) {
  assert(typeof rule.id === "string" && /^[a-z][a-z0-9_]+$/.test(rule.id), `Invalid alert id: ${rule.id}`);
  assert(!seen.has(rule.id), `Duplicate alert id: ${rule.id}`);
  seen.add(rule.id);
  assert(typeof rule.name === "string" && rule.name.trim(), `${rule.id} missing name.`);
  assert(severities.has(rule.severity), `${rule.id} has invalid severity.`);
  assert(typeof rule.metric === "string" && rule.metric.includes("."), `${rule.id} metric should be namespaced.`);
  assert(operators.has(rule.operator), `${rule.id} has invalid operator.`);
  assert(typeof rule.threshold === "number", `${rule.id} threshold must be numeric.`);
  assert(/^\d+[mhd]$/.test(rule.window), `${rule.id} window must look like 5m, 1h, or 1d.`);
  assert(Array.isArray(rule.channels) && rule.channels.length > 0, `${rule.id} must define channels.`);
  assert(typeof rule.runbook === "string" && rule.runbook.trim(), `${rule.id} must define runbook.`);
  const runbookFile = rule.runbook.split("#")[0];
  assert(existsSync(join(root, runbookFile)), `${rule.id} runbook does not exist: ${runbookFile}`);
}

console.log(`Checked ${alerts.rules.length} alert rule(s).`);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}
