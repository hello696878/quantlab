import type { Metadata } from "next";
import "./globals.css";

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
    <html lang="en" data-accent="blue">
      <head>
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
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
