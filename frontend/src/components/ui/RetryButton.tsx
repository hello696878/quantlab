"use client";

import type { ButtonHTMLAttributes } from "react";

interface RetryButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label?: string;
}

export default function RetryButton({
  label = "Retry",
  className = "",
  type = "button",
  ...props
}: RetryButtonProps) {
  return (
    <button
      {...props}
      type={type}
      className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors hover:brightness-125 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
      style={{
        background: "var(--accent-soft)",
        border: "1px solid var(--accent-line)",
        color: "var(--accent-text)",
        ...props.style,
      }}
    >
      {label}
    </button>
  );
}
