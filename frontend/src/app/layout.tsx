import type { Metadata } from "next";
import "./globals.css";
import AppErrorBoundary from "@/components/AppErrorBoundary";
import ToastProvider from "@/components/ToastProvider";

export const metadata: Metadata = {
  title: "QuantLab — Research Terminal",
  description:
    "Interactive quantitative research and backtesting platform. Run strategies on real historical data with no lookahead bias.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-accent="cyan" suppressHydrationWarning>
      <head>
        {/* Apply the saved theme accent before first paint (no flash). Reads the
            same localStorage key as lib/settings.ts; falls back to the default
            accent on any error. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "(function(){try{var a='cyan';var raw=localStorage.getItem('quantlab.settings.v1');" +
              "if(raw){var p=JSON.parse(raw);if(p&&typeof p.accent_color==='string')a=p.accent_color;}" +
              "if(['cyan','blue','emerald','violet','amber','risk'].indexOf(a)===-1)a='cyan';" +
              "document.documentElement.setAttribute('data-accent',a);}catch(e){}})();",
          }}
        />
        {/* Design-system fonts: Manrope (UI) + JetBrains Mono (data/figures).
            Loaded via <link> so an offline build still succeeds (system
            fallbacks apply at runtime). */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      {/* The dark background, aurora, and grid come from globals.css (body::before/::after). */}
      <body className="min-h-screen">
        <AppErrorBoundary>
          <ToastProvider>{children}</ToastProvider>
        </AppErrorBoundary>
      </body>
    </html>
  );
}
