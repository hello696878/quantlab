"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { dismissToast, type Toast, type ToastType } from "@/lib/toast";
import { useToasts } from "@/hooks/useToasts";

// Semantic accent per toast type (neon terminal palette).
const ACCENT: Record<ToastType, string> = {
  success: "var(--pos)",
  error: "var(--neg)",
  warning: "#fbbf24",
  info: "var(--accent)",
};

const ICON: Record<ToastType, string> = {
  success: "M4 12l5 5L20 6", // check
  error: "M6 6l12 12M18 6L6 18", // x
  warning: "M12 4l9 16H3L12 4Zm0 6v4m0 3v.5", // triangle !
  info: "M12 8h.01M11 12h1v5h1", // i
};

function ToastCard({ toast }: { toast: Toast }) {
  const [paused, setPaused] = useState(false);
  const accent = ACCENT[toast.type];

  // Auto-dismiss timer (re-armed on refresh via createdAt; paused on hover).
  useEffect(() => {
    if (!toast.duration || toast.duration <= 0 || paused) return;
    const id = setTimeout(() => dismissToast(toast.id), toast.duration);
    return () => clearTimeout(id);
  }, [toast.id, toast.duration, toast.createdAt, paused]);

  return (
    <div
      className="rise pointer-events-auto flex w-[340px] max-w-[90vw] gap-3 rounded-xl p-3.5"
      style={{
        background: "rgba(10,14,24,0.96)",
        border: "1px solid var(--line-strong)",
        borderLeft: `3px solid ${accent}`,
        boxShadow: "var(--sh-md)",
      }}
      role="status"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <svg
        width={16}
        height={16}
        viewBox="0 0 24 24"
        fill="none"
        stroke={accent}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="mt-0.5 flex-shrink-0"
        aria-hidden
      >
        <path d={ICON[toast.type]} />
      </svg>

      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
          {toast.title}
        </p>
        {toast.description && (
          <p className="mt-0.5 text-xs leading-relaxed" style={{ color: "var(--text-mut)" }}>
            {toast.description}
          </p>
        )}
        {toast.action && (
          <button
            type="button"
            onClick={() => {
              toast.action?.onClick();
              dismissToast(toast.id);
            }}
            className="mt-2 rounded-md px-2 py-1 text-xs font-semibold transition-colors"
            style={{ border: `1px solid ${accent}`, color: accent }}
          >
            {toast.action.label}
          </button>
        )}
      </div>

      <button
        type="button"
        onClick={() => dismissToast(toast.id)}
        aria-label="Dismiss notification"
        className="-mr-1 -mt-1 flex-shrink-0 self-start px-1 text-sm leading-none transition-colors hover:brightness-150"
        style={{ color: "var(--text-mut)" }}
      >
        ✕
      </button>
    </div>
  );
}

export default function ToastViewport() {
  const [mounted, setMounted] = useState(false);
  const toasts = useToasts();

  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  return createPortal(
    <div
      className="pointer-events-none fixed bottom-4 right-4 z-[200] flex flex-col gap-2.5"
      aria-live="polite"
      aria-atomic="false"
    >
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} />
      ))}
    </div>,
    document.body,
  );
}
