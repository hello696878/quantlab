import { redirect } from "next/navigation";

/**
 * `/globe` convenience entry point (e.g. `/globe?market=tw`, `/globe?tour=asia`,
 * `/globe?market=tw&presentation=1`).
 *
 * QuantLab renders as a single workspace-switching page at `/`, so this thin
 * route normalises the friendly globe URL to the canonical query form
 * (`/?view=globe&…`) the app reads, preserving the `market`, `tour`, and
 * `presentation` params. Unknown market/tour ids are passed through unchanged —
 * the globe panel falls back gracefully and shows a friendly notice. No data is
 * fetched here.
 */

export const dynamic = "force-dynamic";

function first(value: string | string[] | undefined): string | undefined {
  return (Array.isArray(value) ? value[0] : value)?.trim() || undefined;
}

export default function GlobeRedirect({
  searchParams,
}: {
  searchParams?: { market?: string | string[]; tour?: string | string[]; presentation?: string | string[] };
}) {
  const params = new URLSearchParams();
  params.set("view", "globe");
  const market = first(searchParams?.market);
  const tour = first(searchParams?.tour);
  const presentation = first(searchParams?.presentation);
  if (market) params.set("market", market);
  if (tour) params.set("tour", tour);
  if (presentation === "1") params.set("presentation", "1");
  redirect(`/?${params.toString()}`);
}
