import { redirect } from "next/navigation";

/**
 * `/globe` and `/globe?market=<id>` convenience entry points.
 *
 * QuantLab renders as a single workspace-switching page at `/`, so this thin
 * route simply normalises the friendly globe URL to the canonical query form
 * (`/?view=globe&market=<id>`) the app reads. Unknown market ids are passed
 * through unchanged — the globe panel falls back to the default market and shows
 * a "Market not found" notice. No data is fetched here.
 */

export const dynamic = "force-dynamic";

export default function GlobeRedirect({
  searchParams,
}: {
  searchParams?: { market?: string | string[] };
}) {
  const raw = searchParams?.market;
  const market = (Array.isArray(raw) ? raw[0] : raw)?.trim();
  redirect(
    market
      ? `/?view=globe&market=${encodeURIComponent(market)}`
      : "/?view=globe",
  );
}
