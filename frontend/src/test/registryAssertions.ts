/** Small test-only contracts shared by live-source checks and mutation fixtures. */
export function assertUniqueIds(ids: readonly string[], surface: string): void {
  const invalid = ids.filter((id, i) => !/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(id) || ids.indexOf(id) !== i);
  if (invalid.length) throw new Error(`${surface}: invalid or duplicate IDs ${JSON.stringify(invalid)}`);
}

export function assertMappings(expected: readonly string[], actual: readonly string[], surface: string): void {
  assertUniqueIds(actual, surface);
  const missing = expected.filter((id) => !actual.includes(id));
  const stale = actual.filter((id) => !expected.includes(id));
  if (missing.length || stale.length) throw new Error(`${surface}: missing [${missing.join(", ")}], stale [${stale.join(", ")}]`);
}

export function publicIds(visibility: Readonly<Record<string, string>>): string[] {
  const invalid = Object.entries(visibility).filter(([, v]) => v !== "sidebar" && v !== "internal");
  if (invalid.length) throw new Error(`Invalid workspace visibility: ${JSON.stringify(invalid)}`);
  return Object.keys(visibility).filter((id) => visibility[id] === "sidebar");
}

export function assertPublicTargets(targets: readonly string[], visibility: Readonly<Record<string, string>>, surface: string): void {
  const visible = publicIds(visibility);
  const invalid = targets.filter((id) => !visible.includes(id));
  if (invalid.length) throw new Error(`${surface}: unknown or internal targets [${invalid.join(", ")}]`);
}

export function assertCommandIdentities(commands: readonly { title: string }[]): void {
  const titles = commands.map((c) => c.title);
  if (titles.some((t, i) => !t.trim() || titles.indexOf(t) !== i)) throw new Error("Palette command titles must be nonempty and unique (nav-title identity)");
}
