"use client";

/**
 * Compact, non-blocking amber warning shown whenever a short-enabled mode
 * (short_only / long_short) is active — near the mode selector, on results, and
 * in Strategy Comparison.  Wording is shared so it stays consistent everywhere.
 */
export default function ShortSellingWarning({
  className,
}: {
  className?: string;
}) {
  return (
    <div
      className={
        "flex gap-2.5 rounded-lg border border-amber-200 bg-amber-50 p-3 " +
        (className ?? "")
      }
    >
      <span className="mt-0.5 flex-shrink-0 text-amber-500">⚠</span>
      <p className="text-xs text-amber-800">
        <span className="font-semibold">Short-selling simulation:</span> borrow
        costs, margin requirements, liquidation risk, and funding costs are not
        modelled. Long/short results may be highly sensitive to timing and
        transaction costs.
      </p>
    </div>
  );
}
