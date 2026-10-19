"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { checkDemoBuild } = require("./check-demo-build.cjs");
const env = { BACKEND_URL: "http://demo-backend:8000", NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE: "read_only_demo" };
const rewrite = { source: "/api/:path*", destination: "http://demo-backend:8000/:path*", regex: "^/api(?:/((?:[^/]+?)(?:/(?:[^/]+?))*))?(?:/)?$" };
const canonical = { source: "/:path+/", destination: "/:path+", internal: true, statusCode: 308, regex: "^(?:/((?:[^/]+?)(?:/(?:[^/]+?))*))/$" };
function manifest(rewrites = [rewrite]) {
  return { version: 3, basePath: "", headers: [], redirects: [canonical], rewrites };
}

// Use the installed locked Next route loader/compiler, without a build or
// server, so the accepted fixture is checked against real config semantics.
async function generatedManifest(overrides = {}) {
  const { defaultConfig } = require("next/dist/server/config-shared");
  const loadCustomRoutes = require("next/dist/lib/load-custom-routes").default;
  const { buildCustomRoute } = require("next/dist/lib/build-custom-route");
  const previous = process.env.BACKEND_URL;
  process.env.BACKEND_URL = env.BACKEND_URL;
  try {
    const config = { ...defaultConfig, ...require("../next.config.js"), ...overrides };
    const routes = await loadCustomRoutes(config);
    return JSON.parse(JSON.stringify({
      version: 3, basePath: config.basePath,
      headers: routes.headers.map((route) => buildCustomRoute("header", route)),
      redirects: routes.redirects.map((route) => buildCustomRoute("redirect", route, ["/_next"])),
      rewrites: Object.fromEntries(Object.entries(routes.rewrites).map(([key, values]) =>
        [key, values.map((route) => buildCustomRoute("rewrite", route))])),
    }));
  } finally {
    if (previous === undefined) delete process.env.BACKEND_URL;
    else process.env.BACKEND_URL = previous;
  }
}

test("accepts the compiled Next grouped rewrite and records the build mode", () => {
  assert.equal(checkDemoBuild(manifest({ beforeFiles: [], afterFiles: [rewrite], fallback: [] }), env).expected_mode, "read_only_demo");
});
test("accepts a legacy array only with the same single exact rewrite", () => {
  assert.equal(checkDemoBuild(manifest(), env).backend_url, env.BACKEND_URL);
});
for (const value of [undefined, "local", ""]) {
  test(`refuses missing or incorrect build mode: ${String(value)}`, () => {
    assert.throws(() => checkDemoBuild(manifest(), { ...env, NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE: value }));
  });
}
test("runtime-looking environment cannot repair a compiled localhost target", () => {
  assert.throws(() => checkDemoBuild(manifest([{ ...rewrite, destination: "http://localhost:8000/:path*" }]), env));
});
test("rejects a build whose backend argument differs from the private service", () => {
  assert.throws(() => checkDemoBuild(manifest(), { ...env, BACKEND_URL: "http://backend:8000" }));
});
for (const value of [{}, null, manifest([rewrite, rewrite]), manifest({ afterFiles: [rewrite] }), manifest([{ ...rewrite, source: "/other" }])]) {
  test(`rejects unsupported or extra rewrites: ${JSON.stringify(value)}`, () => {
    assert.throws(() => checkDemoBuild(value, env));
  });
}

test("accepts the actual repository config through the locked Next route compiler", async () => {
  assert.equal(checkDemoBuild(await generatedManifest(), env).backend_url, env.BACKEND_URL);
});
test("refuses changed compiled redirect regex despite unchanged route labels", async () => {
  const value = await generatedManifest();
  value.redirects[0].regex = "^/api(?:/.*)?$";
  assert.equal(value.redirects[0].source, canonical.source);
  assert.equal(value.redirects[0].destination, canonical.destination);
  assert.throws(() => checkDemoBuild(value, env), /route preconditions/);
});
test("refuses changed compiled rewrite regex despite unchanged route labels", async () => {
  const value = await generatedManifest();
  value.rewrites.afterFiles[0].regex = "^/other(?:/.*)?$";
  assert.equal(value.rewrites.afterFiles[0].source, rewrite.source);
  assert.equal(value.rewrites.afterFiles[0].destination, rewrite.destination);
  assert.throws(() => checkDemoBuild(value, env), /rewrite mismatch/);
});
for (const destination of ["https://external.invalid/:path*", "http://localhost:8000/:path*", "/other/:path*"]) {
  test(`refuses a generated redirect that shadows the valid private rewrite: ${destination}`, async () => {
    const value = await generatedManifest({ redirects: async () => [{ source: "/api/:path*", destination, permanent: false }] });
    assert.equal(value.rewrites.afterFiles[0].destination, rewrite.destination);
    assert.throws(() => checkDemoBuild(value, env), /route preconditions/);
  });
}
for (const condition of ["has", "missing"]) {
  test(`refuses a generated ${condition} condition that makes the private proxy conditional`, async () => {
    const value = await generatedManifest({ rewrites: async () => [{
      source: rewrite.source, destination: rewrite.destination,
      [condition]: [{ type: "header", key: "x-unexpected-condition" }],
    }] });
    assert.equal(value.rewrites.afterFiles[0].destination, rewrite.destination);
    assert.throws(() => checkDemoBuild(value, env), /rewrite mismatch/);
  });
}
for (const change of [
  { headers: [{ source: "/api/:path*", headers: [{ key: "Location", value: "https://external.invalid" }] }] },
  { basePath: "/other" },
  { redirects: [] },
  { redirects: [{ ...canonical, has: [{ type: "header", key: "x-condition" }] }] },
  { rewrites: { beforeFiles: [rewrite], afterFiles: [], fallback: [] } },
  { rewrites: { beforeFiles: [], afterFiles: [], fallback: [rewrite] } },
]) {
  test(`refuses a changed compiled route precondition: ${JSON.stringify(change)}`, () => {
    assert.throws(() => checkDemoBuild({ ...manifest(), ...change }, env));
  });
}
