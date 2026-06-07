// ---------------------------------------------------------------------------
// Global toast store (framework-agnostic, module-level pub/sub).
//
// Lets any code — components OR plain functions (e.g. API error handlers) —
// fire a toast without prop drilling or context.  A React adapter lives in
// `hooks/useToasts.ts`; the rendering UI lives in `components/ToastViewport`.
//
// This is purely UI feedback: it never touches quant results or saved data.
// ---------------------------------------------------------------------------

export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface ToastInput {
  type?: ToastType;
  title: string;
  description?: string;
  action?: ToastAction;
  /** ms before auto-dismiss; 0 disables it.  Defaults per type. */
  duration?: number;
  /**
   * When set, a new toast with the same key refreshes the existing one instead
   * of stacking, and is briefly suppressed after a manual dismiss.  Used to
   * keep repeated "backend offline" notifications from spamming the stack.
   */
  dedupeKey?: string;
}

export interface Toast extends Required<Pick<ToastInput, "title" | "type">> {
  id: number;
  description?: string;
  action?: ToastAction;
  duration: number;
  dedupeKey?: string;
  createdAt: number;
}

type Listener = (toasts: Toast[]) => void;

const DEFAULT_DURATION: Record<ToastType, number> = {
  success: 4000,
  info: 4500,
  warning: 6000,
  error: 7000,
};

const MAX_TOASTS = 5;
const DISMISS_COOLDOWN_MS = 5000;

let toasts: Toast[] = [];
const listeners = new Set<Listener>();
const suppressUntil: Record<string, number> = {};
let nextId = 1;

function emit(): void {
  listeners.forEach((l) => l(toasts));
}

export function subscribeToasts(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Current snapshot (stable reference until the list changes). */
export function getToasts(): Toast[] {
  return toasts;
}

export function pushToast(input: ToastInput): number {
  const type = input.type ?? "info";
  const key = input.dedupeKey;

  if (key) {
    // Recently dismissed → swallow re-fires for a short cooldown.
    if (suppressUntil[key] && Date.now() < suppressUntil[key]) return -1;

    const existing = toasts.find((t) => t.dedupeKey === key);
    if (existing) {
      // Refresh the existing toast in place rather than stacking a duplicate.
      toasts = toasts.map((t) =>
        t.id === existing.id
          ? {
              ...t,
              type,
              title: input.title,
              description: input.description,
              action: input.action,
              duration: input.duration ?? t.duration,
              createdAt: Date.now(),
            }
          : t,
      );
      emit();
      return existing.id;
    }
  }

  const id = nextId++;
  const toast: Toast = {
    id,
    type,
    title: input.title,
    description: input.description,
    action: input.action,
    duration: input.duration ?? DEFAULT_DURATION[type],
    dedupeKey: key,
    createdAt: Date.now(),
  };
  toasts = [...toasts, toast].slice(-MAX_TOASTS);
  emit();
  return id;
}

export function dismissToast(id: number): void {
  const target = toasts.find((t) => t.id === id);
  if (target?.dedupeKey) {
    suppressUntil[target.dedupeKey] = Date.now() + DISMISS_COOLDOWN_MS;
  }
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}

export function clearToasts(): void {
  toasts = [];
  emit();
}

// ── Convenience API ─────────────────────────────────────────────────────────

type ToastOpts = Omit<ToastInput, "type" | "title" | "description">;

export const toast = {
  success: (title: string, description?: string, opts?: ToastOpts) =>
    pushToast({ ...opts, type: "success", title, description }),
  error: (title: string, description?: string, opts?: ToastOpts) =>
    pushToast({ ...opts, type: "error", title, description }),
  warning: (title: string, description?: string, opts?: ToastOpts) =>
    pushToast({ ...opts, type: "warning", title, description }),
  info: (title: string, description?: string, opts?: ToastOpts) =>
    pushToast({ ...opts, type: "info", title, description }),
};

/**
 * Consistent, de-duplicated "backend offline" toast.  Repeated calls collapse
 * into a single notification (and are suppressed briefly after dismissal), so a
 * burst of failed requests never spams the stack.
 */
export function notifyBackendOffline(opts?: { onRetry?: () => void }): void {
  pushToast({
    type: "warning",
    dedupeKey: "backend-offline",
    title: "Backend offline",
    description:
      "Saved resources and API-powered tools require the FastAPI backend.",
    action: opts?.onRetry
      ? { label: "Retry", onClick: opts.onRetry }
      : undefined,
    duration: 6000,
  });
}
