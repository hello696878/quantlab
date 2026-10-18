"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { checkDemoBuild } = require("./check-demo-build.cjs");
const env = { BACKEND_URL: "http://demo-backend:8000", NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE: "read_only_demo" };
const rewrite = { source: "/api/:path*", destination: "http://demo-backend:8000/:path*" };

test("accepts the compiled Next grouped rewrite and records the build mode", () => {
  assert.equal(checkDemoBuild({ rewrites: { beforeFiles: [], afterFiles: [rewrite], fallback: [] } }, env).expected_mode, "read_only_demo");
});
test("accepts a legacy array only with the same single exact rewrite", () => {
  assert.equal(checkDemoBuild({ rewrites: [rewrite] }, env).backend_url, env.BACKEND_URL);
});
for (const value of [undefined, "local", ""]) {
  test(`refuses missing or incorrect build mode: ${String(value)}`, () => {
    assert.throws(() => checkDemoBuild({ rewrites: [rewrite] }, { ...env, NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE: value }));
  });
}
test("runtime-looking environment cannot repair a compiled localhost target", () => {
  assert.throws(() => checkDemoBuild({ rewrites: [{ ...rewrite, destination: "http://localhost:8000/:path*" }] }, env));
});
test("rejects a build whose backend argument differs from the private service", () => {
  assert.throws(() => checkDemoBuild({ rewrites: [rewrite] }, { ...env, BACKEND_URL: "http://backend:8000" }));
});
for (const manifest of [{}, null, { rewrites: [rewrite, rewrite] }, { rewrites: { afterFiles: [rewrite] } }, { rewrites: [{ ...rewrite, source: "/other" }] }]) {
  test(`rejects unsupported or extra rewrites: ${JSON.stringify(manifest)}`, () => {
    assert.throws(() => checkDemoBuild(manifest, env));
  });
}
