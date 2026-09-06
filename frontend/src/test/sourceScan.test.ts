import { describe, expect, it } from "vitest";
import { isProductionSource, parseNavDataTargets, parseNavLiterals, parseSwitcherViewIds, parseViewMetaKeys, parseViewUnionIds } from "./sourceScan";

describe("navigation source scans", () => {
  it.each(["\n", "\r\n"])("handles quotes, whitespace and line endings %j without counting comments or prose", (eol) => {
    const source = [
      '// export type View = "fake";',
      'const prose = "view === \\\"fake\\\"";',
      "export type View = 'home' | 'risk' | 'risklab';",
      "const VIEW_META: Record<View, { title: string }> = { 'home': { title: 'Hi' }, risk: {}, risklab: {} };",
      'if (view === "globe") clearGlobeUrl();',
      "const page = <>{/* view === 'ghost' && <Ghost/> */}{view === 'home' && (<Home/>)}{view === 'risk' && <Risk/>}{view === 'risklab' && <Lab/>}</>;",
    ].join(eol);
    expect(parseViewUnionIds(source)).toEqual(["home", "risk", "risklab"]);
    expect(parseViewMetaKeys(source)).toEqual(["home", "risk", "risklab"]);
    expect(parseSwitcherViewIds(source)).toEqual(["home", "risk", "risklab"]);
  });

  it("cannot use a navigation side effect to replace a deleted render branch", () => {
    expect(parseSwitcherViewIds('if(view === "globe") leave(); const page=<>{view === "home" && <Home/>}</>;')).toEqual(["home"]);
    expect(() => parseSwitcherViewIds('if(view === "globe") leave();')).toThrow(/render branches/);
  });

  it("retains invalid and duplicate literal identities for validation", () => {
    expect(parseViewUnionIds("export type View = '' | 'Home' | 'bad/path' | 'home' | 'home';")).toEqual(["", "Home", "bad/path", "home", "home"]);
  });

  it.each(["export type Other = 'home';", "export type View = string;", "export type View = 'home' | ;"])("fails loudly for unsupported or malformed types: %s", (source) => {
    expect(() => parseViewUnionIds(source)).toThrow();
  });

  it("rejects computed/spread header maps instead of partially reading them", () => {
    expect(() => parseViewMetaKeys("const VIEW_META = {...other, home: {}};")).toThrow(/explicit/);
  });

  it("reads optional calls, single quotes and data-table targets, not comments or text", () => {
    const source = "// onNav('fake')\n const s = \"onNav('prose')\"; onNav ?. ( 'risklab' ); onNav(''); handleNav ('home'); const cards = [{ view: 'risk' as View }];";
    expect(parseNavLiterals(source, "onNav")).toEqual(["risklab", ""]);
    expect(parseNavLiterals(source, "handleNav")).toEqual(["home"]);
    expect(parseNavDataTargets(source, "view")).toEqual(["risk"]);
    expect(() => parseNavDataTargets("const cards = [{route: runtimeValue}];", "route")).toThrow(/literal/);
  });

  it.each(["Card.test.tsx", "Card.spec.tsx", "__tests__/Card.tsx", "fixtures/Card.tsx", "generated/Card.tsx", "node_modules/Card.tsx", ".next/Card.tsx", "test/Card.tsx"])("ignores non-production input %s on both path styles", (path) => {
    expect(isProductionSource(`components/${path}`)).toBe(false);
    expect(isProductionSource(`components/${path}`.replaceAll("/", "\\"))).toBe(false);
  });

  it("includes real source on both path styles", () => {
    expect(isProductionSource("components/panels/Card.tsx")).toBe(true);
    expect(isProductionSource("components\\panels\\Card.tsx")).toBe(true);
  });
});
