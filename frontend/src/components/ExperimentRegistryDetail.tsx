"use client";

import { useEffect, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type ExperimentFull,
  type ReproducibilityAssessment,
  getReproducibility,
  invalidateExperiment,
  markBaseline,
  deleteExperiment,
  formatDuration,
  formatTimestamp,
} from "@/lib/experimentRegistry";
import { notifyBackendOffline, toast } from "@/lib/toast";
import {
  type ExperimentLink,
  listExperimentDatasets,
} from "@/lib/datasetRegistry";
import {
  BaselineBadge,
  CopyValue,
  DetailSection,
  JsonBlock,
  KeyValueTable,
  ReproBadge,
  StatusBadge,
} from "@/components/ExperimentRegistryShared";

interface Props {
  experiment: ExperimentFull;
  onBack: () => void;
  onChanged: (updated: ExperimentFull | null) => void;
  onCompareWith: (id: number) => void;
}

const REPRO_DISCLAIMER =
  "Reproducibility here is repository-level metadata validation only — it is not a claim of scientific reproducibility, an audit, or model correctness.";

export default function ExperimentRegistryDetail({
  experiment,
  onBack,
  onChanged,
  onCompareWith,
}: Props) {
  const exp = experiment;
  const [assessment, setAssessment] = useState<ReproducibilityAssessment | null>(null);
  const [assessError, setAssessError] = useState<string | null>(null);
  const [datasetLinks, setDatasetLinks] = useState<ExperimentLink[]>([]);
  const [busy, setBusy] = useState(false);
  const [showJson, setShowJson] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setAssessment(null);
    setAssessError(null);
    getReproducibility(exp.id)
      .then((a) => {
        if (!cancelled) setAssessment(a);
      })
      .catch((err) => {
        if (!cancelled) setAssessError(classifyApiError(err).message);
      });
    setDatasetLinks([]);
    // Dataset links are best-effort context — a failure here never blocks the detail.
    listExperimentDatasets(exp.id)
      .then((links) => {
        if (!cancelled) setDatasetLinks(links);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [exp.id]);

  async function runAction(
    label: string,
    fn: () => Promise<ExperimentFull | { deleted: boolean }>,
    { removed = false }: { removed?: boolean } = {},
  ) {
    setBusy(true);
    try {
      const result = await fn();
      toast.success(label, `"${exp.name}" updated.`);
      if (removed) {
        onChanged(null);
      } else {
        onChanged(result as ExperimentFull);
      }
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error(`${label} failed`, cls.message);
    } finally {
      setBusy(false);
    }
  }

  const canBaseline = exp.status === "completed" && !exp.is_baseline;
  const canInvalidate = exp.status !== "invalidated";

  return (
    <div className="space-y-4">
      {/* Header / actions */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onBack}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            ← Back to registry
          </button>
          <button
            type="button"
            onClick={() => onCompareWith(exp.id)}
            className="rounded-md border border-blue-200 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50"
          >
            Compare with…
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canBaseline && (
            <button
              type="button"
              disabled={busy}
              onClick={() => runAction("Marked baseline", () => markBaseline(exp.id))}
              className="rounded-md border border-indigo-200 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
            >
              ★ Mark as baseline
            </button>
          )}
          {canInvalidate && (
            <button
              type="button"
              disabled={busy}
              onClick={() => runAction("Invalidated", () => invalidateExperiment(exp.id))}
              className="rounded-md border border-amber-200 px-3 py-1.5 text-sm font-medium text-amber-700 hover:bg-amber-50 disabled:opacity-50"
            >
              Invalidate
            </button>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              if (confirm(`Delete "${exp.name}"? This cannot be undone.`)) {
                runAction("Deleted", () => deleteExperiment(exp.id), { removed: true });
              }
            }}
            className="rounded-md border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Identity */}
      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-xl font-bold text-slate-900">{exp.name}</h2>
            <p className="mt-0.5 text-sm text-slate-500">
              {exp.module} · {exp.experiment_type}
            </p>
            {exp.description && (
              <p className="mt-2 max-w-2xl text-sm text-slate-600">{exp.description}</p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={exp.status} />
            <ReproBadge status={exp.reproducibility_status} />
            <BaselineBadge active={exp.is_baseline} />
          </div>
        </div>
        {exp.error_message && (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <span className="font-semibold">Error:</span> {exp.error_message}
          </div>
        )}
      </div>

      {/* Reproducibility assessment */}
      <DetailSection title="Reproducibility assessment">
        {assessError ? (
          <p className="text-sm text-red-600">{assessError}</p>
        ) : assessment ? (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <ReproBadge status={assessment.status} />
              {assessment.reference_id !== null && (
                <span className="text-xs text-slate-500">
                  vs reference #{assessment.reference_id}
                </span>
              )}
            </div>
            <p className="text-sm text-slate-600">{assessment.summary}</p>
            {assessment.checks.length > 0 && (
              <ul className="flex flex-wrap gap-2 pt-1">
                {assessment.checks.map((c) => (
                  <li
                    key={c.name}
                    className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-600"
                  >
                    {c.name}: <span className="font-medium">{c.state}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="pt-1 text-xs text-slate-400">{REPRO_DISCLAIMER}</p>
          </div>
        ) : (
          <p className="text-sm text-slate-400">Assessing…</p>
        )}
      </DetailSection>

      {/* Fingerprints + provenance grid */}
      <div className="grid gap-4 md:grid-cols-2">
        <DetailSection title="Fingerprints">
          <dl className="space-y-2 text-sm">
            <div className="flex items-center justify-between gap-2">
              <dt className="text-slate-500">Configuration</dt>
              <dd>
                <CopyValue value={exp.configuration_fingerprint} />
              </dd>
            </div>
            <div className="flex items-center justify-between gap-2">
              <dt className="text-slate-500">Result</dt>
              <dd>
                <CopyValue value={exp.result_fingerprint} />
              </dd>
            </div>
            <div className="flex items-center justify-between gap-2">
              <dt className="text-slate-500">Dataset</dt>
              <dd>
                <CopyValue value={exp.dataset_fingerprint} />
              </dd>
            </div>
          </dl>
        </DetailSection>

        <DetailSection title="Provenance & lineage">
          <dl className="space-y-2 text-sm">
            <Row label="Git commit" value={exp.git_commit ? exp.git_commit.slice(0, 12) : "—"} mono />
            <Row label="App version" value={exp.app_version ?? "—"} />
            <Row label="Dataset" value={dataset(exp)} />
            <Row label="Random seed" value={exp.random_seed === null ? "—" : String(exp.random_seed)} mono />
            <Row
              label="Parent"
              value={exp.parent_experiment_id === null ? "—" : `#${exp.parent_experiment_id}`}
            />
          </dl>
        </DetailSection>
      </div>

      {/* Timing */}
      <DetailSection title="Timing">
        <dl className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <Row label="Created" value={formatTimestamp(exp.created_at)} />
          <Row label="Started" value={formatTimestamp(exp.started_at)} />
          <Row label="Completed" value={formatTimestamp(exp.completed_at)} />
          <Row label="Duration" value={formatDuration(exp.duration_ms)} />
        </dl>
      </DetailSection>

      {/* Parameters + metrics */}
      <div className="grid gap-4 md:grid-cols-2">
        <DetailSection title="Parameters">
          <KeyValueTable data={exp.parameters} empty="No parameters recorded." />
        </DetailSection>
        <DetailSection title="Metrics">
          <KeyValueTable data={exp.metrics} empty="No metrics recorded." />
        </DetailSection>
      </div>

      {/* Tags + notes */}
      {(exp.tags.length > 0 || exp.notes) && (
        <DetailSection title="Tags & notes">
          {exp.tags.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1.5">
              {exp.tags.map((t) => (
                <span
                  key={t}
                  className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600"
                >
                  {t}
                </span>
              ))}
            </div>
          )}
          {exp.notes && <p className="whitespace-pre-wrap text-sm text-slate-600">{exp.notes}</p>}
        </DetailSection>
      )}

      {/* Linked dataset versions (Phase 49.0 — Dataset Lineage registry) */}
      {datasetLinks.length > 0 && (
        <DetailSection title="Linked datasets">
          <ul className="space-y-1.5">
            {datasetLinks.map((l) => (
              <li key={l.id} className="flex flex-wrap items-center gap-2 text-sm">
                <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
                  {l.role}
                </span>
                <span className="font-medium text-slate-800">
                  {l.dataset_name ?? "dataset"} · {l.version_label ?? `version #${l.dataset_version_id}`}
                </span>
                {l.fingerprint_match === true && (
                  <span className="text-xs text-emerald-600">fingerprint match</span>
                )}
                {l.fingerprint_match === false && (
                  <span className="text-xs text-amber-600">fingerprint mismatch</span>
                )}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-slate-400">
            Recorded in the Dataset Lineage registry — open the Dataset Lineage view for versions, quality, and lineage.
          </p>
        </DetailSection>
      )}

      {/* Raw JSON */}
      <DetailSection
        title="Raw record"
        action={
          <button
            type="button"
            onClick={() => setShowJson((v) => !v)}
            className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            {showJson ? "Hide JSON" : "Show JSON"}
          </button>
        }
      >
        {showJson ? (
          <JsonBlock value={exp} />
        ) : (
          <p className="text-sm text-slate-400">Full provenance record (read-only).</p>
        )}
      </DetailSection>
    </div>
  );
}

function dataset(exp: ExperimentFull): string {
  if (!exp.dataset_name) return "—";
  return exp.dataset_version ? `${exp.dataset_name} (${exp.dataset_version})` : exp.dataset_name;
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className={`truncate text-slate-800 ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}
