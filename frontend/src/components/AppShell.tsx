"use client";

import type { ReactNode } from "react";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";

/** The set of top-level workspaces, driven by the sidebar. */
export type View =
  | "backtest"
  | "sweep"
  | "train-test"
  | "walk-forward"
  | "comparison"
  | "saved";

interface AppShellProps {
  active: View;
  onNav: (view: View) => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
}

/**
 * Dark app shell: fixed sidebar + sticky status bar + scrolling content.
 *
 * Layout truth: a fixed 224px (w-56) sidebar plus a content column offset by
 * the same width (ml-56) in natural document flow.  This renders and
 * screenshots reliably without a nested overflow container.
 */
export default function AppShell({
  active,
  onNav,
  title,
  subtitle,
  children,
}: AppShellProps) {
  return (
    <>
      <Sidebar active={active} onNav={onNav} />

      <div className="ml-56 flex min-h-screen flex-col">
        <TopBar title={title} subtitle={subtitle} />
        <main className="mx-auto w-full max-w-6xl flex-1 px-7 py-8">
          {children}
        </main>
      </div>
    </>
  );
}
