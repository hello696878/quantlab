"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface Command {
  id: string;
  /** Group header the command is listed under (e.g. "Navigation"). */
  group: string;
  title: string;
  /** Extra words matched by the search box but not displayed. */
  keywords?: string;
  /** Optional right-aligned hint (e.g. a shortcut or context label). */
  hint?: string;
  /** Action to run.  Must be safe: navigate / prefill only, never auto-run. */
  run: () => void;
}

/** Window event other components can dispatch to open the palette. */
export const COMMAND_PALETTE_EVENT = "quantlab:command-palette";

/** Open the command palette from anywhere (e.g. a TopBar button). */
export function openCommandPalette(): void {
  try {
    window.dispatchEvent(new Event(COMMAND_PALETTE_EVENT));
  } catch {
    /* non-browser — ignore */
  }
}

/** True on macOS/iOS, used only to render ⌘ vs Ctrl in hints. */
export function useIsMac(): boolean {
  const [isMac, setIsMac] = useState(false);
  useEffect(() => {
    const s = `${navigator.platform} ${navigator.userAgent}`;
    setIsMac(/mac|iphone|ipad|ipod/i.test(s));
  }, []);
  return isMac;
}

// ---------------------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------------------

function matches(cmd: Command, tokens: string[]): boolean {
  if (tokens.length === 0) return true;
  const hay = `${cmd.title} ${cmd.group} ${cmd.keywords ?? ""}`.toLowerCase();
  return tokens.every((t) => hay.includes(t));
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CommandPalette({ commands }: { commands: Command[] }) {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const isMac = useIsMac();

  useEffect(() => setMounted(true), []);

  // Global open shortcut (Ctrl/Cmd+K) + programmatic open event.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault(); // some browsers focus the address bar on Ctrl+K
        setOpen((o) => !o);
      }
    }
    function onOpen() {
      setOpen(true);
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener(COMMAND_PALETTE_EVENT, onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(COMMAND_PALETTE_EVENT, onOpen);
    };
  }, []);

  // On open: clear the query, reset selection, focus the input.
  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    const id = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [open]);

  const filtered = useMemo(() => {
    const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
    return commands.filter((c) => matches(c, tokens));
  }, [commands, query]);

  // Keep the selection inside the (possibly shrunken) filtered list.
  useEffect(() => {
    setActive((i) =>
      filtered.length === 0 ? 0 : Math.min(i, filtered.length - 1),
    );
  }, [filtered.length]);

  // Scroll the active row into view as the selection moves.
  useEffect(() => {
    if (!open) return;
    listRef.current
      ?.querySelector<HTMLElement>(`[data-idx="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  function runAt(i: number) {
    const cmd = filtered[i];
    if (!cmd) return;
    setOpen(false); // close first so the workspace change is visible immediately
    cmd.run();
  }

  function onInputKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    switch (e.key) {
      case "Escape":
        e.preventDefault();
        setOpen(false);
        break;
      case "ArrowDown":
        e.preventDefault();
        setActive((i) => Math.min(i + 1, Math.max(filtered.length - 1, 0)));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActive((i) => Math.max(i - 1, 0));
        break;
      case "Enter":
        e.preventDefault();
        runAt(active);
        break;
    }
  }

  if (!mounted || !open) return null;

  const node = (
    <div
      className="fixed inset-0 z-[130] flex items-start justify-center overflow-y-auto p-4 sm:p-6"
      style={{ background: "rgba(2,4,10,0.66)", backdropFilter: "blur(3px)" }}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onClick={() => setOpen(false)}
    >
      <div
        className="card mt-[8vh] w-full max-w-xl overflow-hidden p-0"
        style={{ boxShadow: "var(--sh-md), var(--panel-glow)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div
          className="flex items-center gap-2.5 px-4 py-3"
          style={{ borderBottom: "1px solid var(--line)" }}
        >
          <svg
            width={16}
            height={16}
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--accent)"
            strokeWidth="2"
            strokeLinecap="round"
            aria-hidden
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKeyDown}
            placeholder="Search commands…"
            spellCheck={false}
            autoComplete="off"
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: "var(--text-hi)" }}
          />
          <kbd
            className="mono rounded px-1.5 py-0.5 text-[10px]"
            style={{
              background: "var(--glass)",
              border: "1px solid var(--line)",
              color: "var(--text-mut)",
            }}
          >
            esc
          </kbd>
        </div>

        {/* Results */}
        {filtered.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-slate-500">
            No commands match “{query}”.
          </div>
        ) : (
          <div ref={listRef} className="max-h-[52vh] overflow-y-auto px-1.5 py-1.5">
            {filtered.map((cmd, i) => {
              const showHeader = i === 0 || filtered[i - 1].group !== cmd.group;
              const selected = i === active;
              return (
                <div key={cmd.id}>
                  {showHeader && (
                    <div
                      className="uplabel px-2.5 pb-1 pt-2"
                      style={{ color: "var(--text-mut)" }}
                    >
                      {cmd.group}
                    </div>
                  )}
                  <button
                    type="button"
                    data-idx={i}
                    onMouseMove={() => setActive(i)}
                    onClick={() => runAt(i)}
                    className="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm"
                    style={
                      selected
                        ? {
                            background: "var(--accent-soft)",
                            border: "1px solid var(--accent-line)",
                            color: "var(--text-hi)",
                          }
                        : { border: "1px solid transparent", color: "var(--text)" }
                    }
                  >
                    <span className="flex-1 truncate">{cmd.title}</span>
                    {cmd.hint && (
                      <span className="mono text-[11px] text-slate-500">
                        {cmd.hint}
                      </span>
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Footer hint */}
        <div
          className="flex items-center gap-3 px-4 py-2 text-[11px]"
          style={{ borderTop: "1px solid var(--line)", color: "var(--text-mut)" }}
        >
          <span className="mono">↑↓</span> navigate
          <span className="mono">↵</span> run
          <span className="mono">esc</span> close
          <span className="ml-auto">{isMac ? "⌘K" : "Ctrl K"}</span>
        </div>
      </div>
    </div>
  );

  return createPortal(node, document.body);
}
