"use client";

import { useEffect, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type DatasetFull,
  type ExperimentLink,
  type LineageGraph,
  type QualityResult,
  type VersionFull,
  type VersionSummary,
  fmtBytes,
  fmtRange,
  fmtTs,
  getDatasetVersion,
  getLineage,
  listDatasetVersions,
  listVersionExperiments,
  listVersionQuality,
  SOURCE_TYPE_LABELS,
} from "@/lib/datasetRegistry";
import {
  CopyValue,
  DetailSection,
  JsonBlock,
  KeyValueTable,
} from "@/components/ExperimentRegistryShared";
import DatasetLineageGraph from "@/components/DatasetLineageGraph";
import { ProvenanceBadge, QualityBadge } from "@/components/DatasetLineageShared";

interface Props {
  dataset: DatasetFull;
  onBack: () => void;
  onCompare: (aId: number, bId: number, label: string) => void;
}

export default function DatasetLineageDetail({ dataset, onBack, onCompare }: Props) {
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [version, setVersion] = useState<VersionFull | null>(null);
  const [graph, setGraph] = useState<LineageGraph | null>(null);
  const [quality, setQuality] = useState<QualityResult[]>([]);
  const [links, setLinks] = useState<ExperimentLink[]>([]);
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listDatasetVersions(dataset.id)
      .then((vs) => {
        if (cancelled) return;
        setVersions(vs);
        const current = vs.find((v) => v.is_current) ?? vs[0];
        if (current) setSelectedId(current.id);
      })
      .catch((err) => !cancelled && setError(classifyApiError(err).message));
    return () => {
      cancelled = true;
    };
  }, [dataset.id]);

  useEffect(() => {
    if (selectedId === null) return;
    let cancelled = false;
    setVersion(null);
    setGraph(null);
    setQuality([]);
    setLinks([]);
    Promise.all([
      getDatasetVersion(selectedId),
      getLineage(selectedId),
      listVersionQuality(selectedId),
      listVersionExperiments(selectedId),
    ])
      .then(([v, g, q, l]) => {
        if (cancelled) return;
        setVersion(v);
        setGraph(g);
        setQuality(q);
        setLinks(l);
      })
      .catch((err) => !cancelled && setError(classifyApiError(err).message));
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  function selectFromGraph(versionId: number) {
    // Node may belong to another dataset — still selectable; version fetch
    // carries its own dataset name so the panel stays truthful.
    setSelectedId(versionId);
  }

  function toggleCompare(id: number) {
    setCompareIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return [prev[1], id];
      return [...prev, id];
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={onBack}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
        >
          ← Back to datasets
        </button>
        <button
          type="button"
          disabled={compareIds.length !== 2}
          onClick={() =>
            onCompare(compareIds[0], compareIds[1], dataset.name)
          }
          className="rounded-md border border-blue-200 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-50"
        >
          Compare selected versions ({compareIds.length}/2)
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      {/* Dataset identity */}
      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-xl font-bold text-slate-900">{dataset.name}</h2>
            <p className="mt-0.5 text-sm text-slate-500">
              {dataset.domain} · {dataset.dataset_type} ·{" "}
              {SOURCE_TYPE_LABELS[dataset.source_type] ?? dataset.source_type}
              {dataset.provider ? ` · ${dataset.provider}` : ""}
            </p>
            {dataset.description && (
              <p className="mt-2 max-w-2xl text-sm text-slate-600">{dataset.description}</p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ProvenanceBadge status={dataset.provenance_status} />
            {dataset.is_demo && (
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-500">
                Demo
              </span>
            )}
          </div>
        </div>
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <Row label="Format" value={dataset.format} />
          <Row label="Frequency" value={dataset.frequency ?? "—"} />
          <Row label="Timezone" value={dataset.timezone ?? "—"} />
          <Row label="Asset class" value={dataset.asset_class ?? "—"} />
          <Row label="Symbols" value={dataset.symbol_scope ?? "—"} />
          <Row label="Schema version" value={dataset.schema_version ?? "—"} />
          <Row
            label="License"
            value={dataset.license_name ?? "—"}
            title={dataset.license_url ?? undefined}
          />
          <Row label="Source ref" value={dataset.source_reference ?? "—"} />
        </dl>
        {dataset.tags.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {dataset.tags.map((t) => (
              <span key={t} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
                {t}
              </span>
            ))}
          </div>
        )}
        {dataset.notes && (
          <p className="mt-3 whitespace-pre-wrap text-sm text-slate-600">{dataset.notes}</p>
        )}
      </div>

      {/* Version history */}
      <DetailSection title={`Version history (${versions.length})`}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th scope="col" className="px-2 py-2 text-center">Cmp</th>
                <th scope="col" className="px-2 py-2 text-left">Version</th>
                <th scope="col" className="px-2 py-2 text-left">Created</th>
                <th scope="col" className="px-2 py-2 text-right">Rows</th>
                <th scope="col" className="px-2 py-2 text-left">Range</th>
                <th scope="col" className="px-2 py-2 text-left">Quality</th>
                <th scope="col" className="px-2 py-2 text-left">Manifest fp</th>
                <th scope="col" className="px-2 py-2 text-left">State</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => (
                <tr
                  key={v.id}
                  className={`border-b border-slate-50 last:border-0 ${v.id === selectedId ? "bg-blue-50/40" : ""}`}
                >
                  <td className="px-2 py-2 text-center">
                    <input
                      type="checkbox"
                      checked={compareIds.includes(v.id)}
                      onChange={() => toggleCompare(v.id)}
                      aria-label={`Select version ${v.version_label} for comparison`}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <button
                      type="button"
                      onClick={() => setSelectedId(v.id)}
                      className="font-medium text-blue-700 hover:underline"
                    >
                      {v.version_label}
                    </button>
                    {v.is_current && (
                      <span className="ml-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-1.5 text-[10px] font-medium text-emerald-700">
                        current
                      </span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-2 py-2 text-xs text-slate-500">{fmtTs(v.created_at).slice(0, 16)}</td>
                  <td className="px-2 py-2 text-right font-mono text-xs">{v.row_count ?? "—"}</td>
                  <td className="whitespace-nowrap px-2 py-2 text-xs text-slate-500">{fmtRange(v.start_time, v.end_time)}</td>
                  <td className="px-2 py-2"><QualityBadge status={v.quality_status} /></td>
                  <td className="px-2 py-2"><CopyValue value={v.manifest_fingerprint} display={v.manifest_fingerprint.slice(0, 12)} /></td>
                  <td className="px-2 py-2 text-xs">
                    {v.invalidated_at ? (
                      <span className="text-red-600">invalidated</span>
                    ) : v.deterministic ? (
                      <span className="text-slate-500">deterministic</span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </DetailSection>

      {/* Selected version */}
      {version && (
        <>
          <div className="card p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <h3 className="text-base font-bold text-slate-900">
                {version.dataset_name ?? dataset.name} · {version.version_label}
                {version.dataset_id !== dataset.id && (
                  <span className="ml-2 text-xs font-normal text-slate-400">(related dataset)</span>
                )}
              </h3>
              <QualityBadge status={version.quality_status} />
            </div>
            {version.invalidated_at && (
              <div className="mt-2 rounded-lg border border-red-200 bg-red-50 p-2.5 text-sm text-red-700">
                Invalidated {fmtTs(version.invalidated_at)} — {version.invalidation_reason ?? "no reason recorded"}.
                The record, its lineage, and its experiment links are preserved.
              </div>
            )}
            <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <Row label="Rows × cols" value={`${version.row_count ?? "—"} × ${version.column_count ?? "—"}`} />
              <Row label="Range" value={fmtRange(version.start_time, version.end_time)} />
              <Row label="Size" value={fmtBytes(version.file_size_bytes)} />
              <Row label="Ingestion" value={version.ingestion_method} />
              <Row label="Locator" value={version.storage_locator} mono />
              <Row label="Deterministic" value={version.deterministic ? "yes" : "no"} />
              <Row label="Validation" value={version.validation_status} />
              <Row label="Compression" value={version.compression ?? "—"} />
            </dl>
            <dl className="mt-3 space-y-2 text-sm">
              <FpRow label="Manifest fingerprint" value={version.manifest_fingerprint} />
              <FpRow label="Schema fingerprint" value={version.schema_fingerprint} />
              <FpRow label="Content fingerprint" value={version.content_fingerprint} />
              <FpRow label="Source fingerprint" value={version.source_fingerprint} />
            </dl>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <DetailSection title="Schema snapshot">
              {version.schema_snapshot.fields && version.schema_snapshot.fields.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        <th scope="col" className="py-1.5 pr-3 text-left">Field</th>
                        <th scope="col" className="py-1.5 pr-3 text-left">Type</th>
                        <th scope="col" className="py-1.5 text-left">Nullable</th>
                      </tr>
                    </thead>
                    <tbody>
                      {version.schema_snapshot.fields.map((f) => (
                        <tr key={f.name} className="border-b border-slate-50 last:border-0">
                          <td className="py-1.5 pr-3 font-mono text-xs">{f.name}</td>
                          <td className="py-1.5 pr-3 text-xs text-slate-600">{f.type}</td>
                          <td className="py-1.5 text-xs text-slate-500">{f.nullable ? "yes" : "no"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-slate-400">No schema snapshot recorded.</p>
              )}
            </DetailSection>

            <DetailSection title="Quality checks">
              {quality.length === 0 ? (
                <p className="text-sm text-slate-400">
                  No quality checks recorded for this version.
                </p>
              ) : (
                <ul className="space-y-1.5">
                  {quality.map((q) => (
                    <li key={q.id} className="flex flex-wrap items-center gap-2 text-sm">
                      <QualityBadge status={q.status} />
                      <span className="font-medium text-slate-700">{q.check_name}</span>
                      {q.message && <span className="text-xs text-slate-500">{q.message}</span>}
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-2 text-xs text-slate-400">
                Checks validate declared structural metadata only — they do not prove the data is correct.
              </p>
            </DetailSection>
          </div>

          <DetailSection title="Lineage">
            {graph ? (
              <DatasetLineageGraph
                graph={graph}
                selectedVersionId={version.id}
                onSelectVersion={selectFromGraph}
              />
            ) : (
              <p className="text-sm text-slate-400">Loading lineage…</p>
            )}
          </DetailSection>

          <DetailSection title="Linked experiments">
            {links.length === 0 ? (
              <p className="text-sm text-slate-400">No experiments linked to this version.</p>
            ) : (
              <ul className="space-y-1.5">
                {links.map((l) => (
                  <li key={l.id} className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
                      {l.role}
                    </span>
                    <span className="font-medium text-slate-800">
                      {l.experiment_name ?? `experiment #${l.experiment_id}`}
                    </span>
                    {l.fingerprint_match === true && (
                      <span className="text-xs text-emerald-600">fingerprint match</span>
                    )}
                    {l.fingerprint_match === false && (
                      <span className="text-xs text-amber-600">fingerprint mismatch</span>
                    )}
                    <span className="text-xs text-slate-400">
                      (open in Experiment Registry to inspect)
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </DetailSection>

          <DetailSection
            title="Provenance & statistics"
            action={
              <button
                type="button"
                onClick={() => setShowRaw((v) => !v)}
                className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
              >
                {showRaw ? "Hide raw JSON" : "Raw JSON"}
              </button>
            }
          >
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Provenance</h4>
                <KeyValueTable data={version.provenance} empty="No provenance recorded (unknown)." />
              </div>
              <div>
                <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Statistics summary</h4>
                <KeyValueTable data={version.statistics_summary} empty="No statistics recorded." />
              </div>
            </div>
            {showRaw && <div className="mt-3"><JsonBlock value={version} /></div>}
          </DetailSection>
        </>
      )}
    </div>
  );
}

function Row({ label, value, mono = false, title }: { label: string; value: string; mono?: boolean; title?: string }) {
  return (
    <div className="flex items-center justify-between gap-2" title={title}>
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd className={`truncate text-slate-800 ${mono ? "font-mono text-xs" : ""}`} title={value}>
        {value}
      </dd>
    </div>
  );
}

function FpRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd className="min-w-0"><CopyValue value={value} /></dd>
    </div>
  );
}
