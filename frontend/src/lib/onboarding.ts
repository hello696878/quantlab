// ---------------------------------------------------------------------------
// Onboarding / guided-demo local state
//
// First-run guidance only.  Everything here is stored in the browser's
// localStorage — no account, no cloud sync, no backend.  None of this affects
// quant results: it only controls which hints/checklist the UI shows.
// ---------------------------------------------------------------------------

const HIDE_KEY = "quantlab.onboarding.hidden";
const CHECK_KEY = "quantlab.onboarding.checklist";

/** Fired (same-tab) whenever onboarding state changes, so open views refresh. */
export const ONBOARDING_EVENT = "quantlab:onboarding";

export type ChecklistStep =
  | "ran_backtest"
  | "saved_backtest"
  | "exported_report"
  | "viewed_risk"
  | "built_strategy";

export type ChecklistState = Record<ChecklistStep, boolean>;

export const EMPTY_CHECKLIST: ChecklistState = {
  ran_backtest: false,
  saved_backtest: false,
  exported_report: false,
  viewed_risk: false,
  built_strategy: false,
};

function storage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

function emit(): void {
  try {
    window.dispatchEvent(new Event(ONBOARDING_EVENT));
  } catch {
    /* non-browser / blocked — ignore */
  }
}

// ── Dismiss state ───────────────────────────────────────────────────────────

export function isOnboardingHidden(): boolean {
  return storage()?.getItem(HIDE_KEY) === "1";
}

export function setOnboardingHidden(hidden: boolean): void {
  const ls = storage();
  if (!ls) return;
  try {
    if (hidden) ls.setItem(HIDE_KEY, "1");
    else ls.removeItem(HIDE_KEY);
  } catch {
    /* ignore quota / privacy errors */
  }
  emit();
}

// ── Quick-start checklist ───────────────────────────────────────────────────

export function getChecklist(): ChecklistState {
  const ls = storage();
  if (!ls) return { ...EMPTY_CHECKLIST };
  try {
    const raw = ls.getItem(CHECK_KEY);
    if (!raw) return { ...EMPTY_CHECKLIST };
    const parsed = JSON.parse(raw) as Partial<ChecklistState>;
    return { ...EMPTY_CHECKLIST, ...parsed };
  } catch {
    return { ...EMPTY_CHECKLIST };
  }
}

/** Mark a checklist step done (idempotent).  Triggered by real user actions. */
export function markChecklistStep(step: ChecklistStep): void {
  const ls = storage();
  if (!ls) return;
  const current = getChecklist();
  if (current[step]) return; // already done — no write, no event
  current[step] = true;
  try {
    ls.setItem(CHECK_KEY, JSON.stringify(current));
  } catch {
    return;
  }
  emit();
}

export function resetChecklist(): void {
  const ls = storage();
  if (!ls) return;
  try {
    ls.removeItem(CHECK_KEY);
  } catch {
    /* ignore */
  }
  emit();
}
