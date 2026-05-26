import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QuantLab — SMA Crossover Backtester",
  description:
    "Interactive quantitative backtesting platform. Run long-only SMA crossover strategies on real historical data.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        {/* ── Top navigation bar ─────────────────────────────────────── */}
        <header className="bg-white border-b border-slate-200 sticky top-0 z-20">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center gap-3">
            {/* Logo mark */}
            <div className="w-7 h-7 rounded-md bg-blue-600 flex items-center justify-center flex-shrink-0">
              <span className="text-white font-bold text-xs">Q</span>
            </div>
            <span className="font-semibold text-slate-900 text-base">
              QuantLab
            </span>
            <span className="hidden sm:inline text-slate-400 text-sm ml-1">
              / SMA Crossover Backtester
            </span>
            <div className="ml-auto flex items-center gap-2">
              <span className="inline-flex items-center gap-1 text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                <span className="w-1.5 h-1.5 bg-green-500 rounded-full inline-block" />
                Phase 1 MVP
              </span>
            </div>
          </div>
        </header>

        {/* ── Main content ───────────────────────────────────────────── */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>

        {/* ── Footer ─────────────────────────────────────────────────── */}
        <footer className="border-t border-slate-200 bg-white mt-12">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between text-xs text-slate-400">
            <span>QuantLab — for research purposes only. Not financial advice.</span>
            <span>Data via Yahoo Finance</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
