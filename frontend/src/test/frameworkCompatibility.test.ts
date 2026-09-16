import { createRequire } from "node:module";
import type { NextConfig } from "next";
import { describe, expect, it, vi } from "vitest";
import postcss from "postcss";
import autoprefixer from "autoprefixer";
import tailwindcss from "tailwindcss";

const require = createRequire(import.meta.url);
const nextConfig = require("../../next.config.js") as NextConfig;

describe("framework dependency compatibility", () => {
  it.each([
    [undefined, "http://localhost:8000"],
    ["http://127.0.0.1:8766", "http://127.0.0.1:8766"],
    ["http://127.0.0.1:8766/", "http://127.0.0.1:8766"],
  ])("retains the backend proxy configuration for %s", async (backend, expected) => {
    vi.stubEnv("BACKEND_URL", backend);
    expect(await nextConfig.rewrites!()).toEqual([
      { source: "/api/:path*", destination: `${expected}/:path*` },
    ]);
  });

  it("uses the patched PostCSS API through Next and the existing Tailwind plugins", async () => {
    const fromNext = createRequire(require.resolve("next/package.json"));
    const nextPostcss: typeof postcss = fromNext("postcss");
    expect(nextPostcss).toBe(postcss);
    const manifest = require("../../package.json");
    expect(manifest.overrides.next.postcss).toBe("$postcss");
    expect(nextPostcss().version).toBe(manifest.devDependencies.postcss);

    const result = await nextPostcss([
      tailwindcss({
        content: [{ raw: '<div class="text-green-500 sm:flex"></div>' }],
        corePlugins: { preflight: false },
      }),
      autoprefixer({ overrideBrowserslist: ["Safari 15"] }),
    ]).process("@tailwind utilities; .selection { user-select: none; }", { from: undefined });

    expect(result.css).toContain(".text-green-500");
    expect(result.css).toContain("@media (min-width: 640px)");
    expect(result.css).toContain("display: flex");
    expect(result.css).toContain("-webkit-user-select: none");
    expect(result.warnings()).toEqual([]);
  });
});
