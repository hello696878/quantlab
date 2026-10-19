"use strict";
const fs = require("node:fs");

const backend = "http://demo-backend:8000";
const mode = "read_only_demo";
// Locked Next 15 route-compiler expressions. The generated-config regression
// checks these against the installed compiler instead of trusting labels alone.
const canonicalRegex = "^(?:/((?:[^/]+?)(?:/(?:[^/]+?))*))/$";
const rewriteRegex = "^/api(?:/((?:[^/]+?)(?:/(?:[^/]+?))*))?(?:/)?$";

function onlyKeys(value, keys) {
  return value !== null && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).every((key) => keys.includes(key));
}

function checkDemoBuild(manifest, env) {
  if (env.BACKEND_URL !== backend || env.NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE !== mode) {
    throw new Error("Demo build environment mismatch");
  }
  // Next applies redirects and headers before its afterFiles rewrites. Checking
  // only the destination would accept a compiled route that never reaches it.
  const redirects = manifest?.redirects;
  const canonical = Array.isArray(redirects) && redirects.length === 1 ? redirects[0] : null;
  if (manifest?.version !== 3 || manifest.basePath !== "" ||
      !Array.isArray(manifest.headers) || manifest.headers.length !== 0 ||
      !onlyKeys(canonical, ["source", "destination", "internal", "statusCode", "regex"]) ||
      canonical.source !== "/:path+/" || canonical.destination !== "/:path+" ||
      canonical.internal !== true || canonical.statusCode !== 308 || canonical.regex !== canonicalRegex) {
    throw new Error("Demo compiled route preconditions mismatch");
  }
  const groups = manifest?.rewrites;
  const entries = Array.isArray(groups) ? groups :
    onlyKeys(groups, ["beforeFiles", "afterFiles", "fallback"]) &&
    ["beforeFiles", "afterFiles", "fallback"].every((k) => Array.isArray(groups[k])) &&
    groups.beforeFiles.length === 0 && groups.fallback.length === 0
      ? groups.afterFiles : [];
  if (entries.length !== 1 || !onlyKeys(entries[0], ["source", "destination", "regex"]) ||
      entries[0]?.source !== "/api/:path*" || entries[0]?.destination !== `${backend}/:path*` ||
      entries[0]?.regex !== rewriteRegex) {
    throw new Error("Demo compiled rewrite mismatch");
  }
  return { schema: "demo_build_contract_v1", backend_url: backend, expected_mode: mode, node: process.version };
}

if (require.main === module) {
  const path = process.argv[2];
  if (!path || fs.statSync(path).size > 1024 * 1024) throw new Error("Missing or oversized route manifest");
  process.stdout.write(JSON.stringify(checkDemoBuild(JSON.parse(fs.readFileSync(path, "utf8")), process.env)) + "\n");
}
module.exports = { checkDemoBuild };
