"use strict";
const fs = require("node:fs");

const backend = "http://demo-backend:8000";
const mode = "read_only_demo";

function checkDemoBuild(manifest, env) {
  if (env.BACKEND_URL !== backend || env.NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE !== mode) {
    throw new Error("Demo build environment mismatch");
  }
  const groups = manifest?.rewrites;
  const entries = Array.isArray(groups) ? groups :
    groups && ["beforeFiles", "afterFiles", "fallback"].every((k) => Array.isArray(groups[k]))
      ? [...groups.beforeFiles, ...groups.afterFiles, ...groups.fallback] : [];
  if (entries.length !== 1 || entries[0]?.source !== "/api/:path*" || entries[0]?.destination !== `${backend}/:path*`) {
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
