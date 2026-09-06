/** Records blocked attempts so an application catch cannot hide a missing mock. */
export function createNetworkGuard() {
  const attempts: string[] = [];
  return {
    block(transport: string): never {
      attempts.push(transport);
      throw new Error(`Unmocked network access (${transport}); mock the specific API client in this offline test.`);
    },
    assertClean(): void {
      const blocked = attempts.splice(0);
      if (blocked.length) throw new Error(`Blocked unmocked network access: ${blocked.join(", ")}`);
    },
  };
}
