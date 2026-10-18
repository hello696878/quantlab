"use client";
import { useEffect, useState, type ReactNode } from "react";
import { loadCapabilities, type ServingCapabilities } from "@/lib/servingCapabilities";
import ReadOnlyDemo from "@/components/ReadOnlyDemo";

/** No research workspace mounts before a fresh, validated backend handshake. */
export default function ServingGate({ children }: { children: ReactNode }) {
  const [capabilities, setCapabilities] = useState<ServingCapabilities | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timeout = setTimeout(() => controller.abort(), 5000);
    setError(null);
    loadCapabilities(controller.signal).then((value) => {
      if (active) setCapabilities(value);
    }).catch((err: unknown) => {
      if (active) setError(err instanceof Error && ["Frontend/backend serving mode mismatch", "Invalid frontend mode configuration"].includes(err.message)
        ? err.message : "Serving capabilities could not be verified. The backend may be unavailable or incompatible.");
    }).finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [retry]);
  if (capabilities?.mode === "local") return <>{children}</>;
  if (capabilities?.mode === "read_only_demo") return <ReadOnlyDemo capabilities={capabilities} />;
  return <main className="mx-auto max-w-xl space-y-4 p-8 text-[var(--text)]">
    <h1 className="text-xl font-semibold text-[var(--text-hi)]">QuantLab</h1>
    {error ? <>
      <p role="alert">{error} Workspaces remain locked; local saved data has not been removed.</p>
      <button type="button" className="btn-secondary" onClick={() => setRetry((v) => v + 1)}>Retry connection</button>
    </> : <p role="status">Checking serving capabilities...</p>}
  </main>;
}
