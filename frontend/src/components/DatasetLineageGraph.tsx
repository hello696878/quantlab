"use client";

import { useMemo, useState } from "react";
import type { LineageGraph, LineageNode } from "@/lib/datasetRegistry";

/**
 * Lightweight SVG lineage visualization (Phase 49.0).
 *
 * Layered layout: ancestors left of the selected node, descendants right,
 * columns by depth, rows within a column. Server-side traversal is already
 * bounded (depth + node limits) and reports truncation; this component only
 * renders what it received. A tabular parents/children fallback below the
 * SVG doubles as the accessible text alternative.
 */

interface Props {
  graph: LineageGraph;
  selectedVersionId: number;
  onSelectVersion: (versionId: number) => void;
}

const NODE_W = 168;
const NODE_H = 46;
const COL_GAP = 70;
const ROW_GAP = 18;
const PAD = 16;

const QUALITY_COLOR: Record<string, string> = {
  passed: "#34d399",
  warning: "#fbbf24",
  failed: "#f87171",
  skipped: "#94a3b8",
  unknown: "#94a3b8",
};

export default function DatasetLineageGraph({ graph, selectedVersionId, onSelectVersion }: Props) {
  const [showTable, setShowTable] = useState(false);

  const layout = useMemo(() => {
    // Column index = depth signed by direction (ancestor −, descendant +).
    const columns = new Map<number, LineageNode[]>();
    for (const node of graph.nodes) {
      const col =
        node.direction === "ancestor" ? -node.depth : node.direction === "descendant" ? node.depth : 0;
      if (!columns.has(col)) columns.set(col, []);
      columns.get(col)!.push(node);
    }
    const colKeys = Array.from(columns.keys()).sort((a, b) => a - b);
    const positions = new Map<number, { x: number; y: number }>();
    let maxRows = 1;
    colKeys.forEach((col, ci) => {
      const nodes = columns.get(col)!;
      nodes.sort((a, b) => a.dataset_name.localeCompare(b.dataset_name) || a.version_id - b.version_id);
      maxRows = Math.max(maxRows, nodes.length);
      nodes.forEach((node, ri) => {
        positions.set(node.version_id, {
          x: PAD + ci * (NODE_W + COL_GAP),
          y: PAD + ri * (NODE_H + ROW_GAP),
        });
      });
    });
    const width = PAD * 2 + colKeys.length * NODE_W + (colKeys.length - 1) * COL_GAP;
    const height = PAD * 2 + maxRows * NODE_H + (maxRows - 1) * ROW_GAP;
    return { positions, width: Math.max(width, NODE_W + PAD * 2), height };
  }, [graph]);

  const byId = useMemo(() => new Map(graph.nodes.map((n) => [n.version_id, n])), [graph]);
  const parents = graph.edges.filter((e) => e.child_version_id === selectedVersionId);
  const children = graph.edges.filter((e) => e.parent_version_id === selectedVersionId);

  if (graph.nodes.length <= 1 && graph.edges.length === 0) {
    return (
      <p className="text-sm text-slate-400">
        No lineage recorded for this version — it has no registered parents or children.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-slate-400">
          Directed parent → child lineage.
          {graph.truncated &&
            ` Truncated at depth ${graph.max_depth} / ${graph.node_limit} nodes — follow the tables for the rest.`}
        </p>
        <button
          type="button"
          onClick={() => setShowTable((v) => !v)}
          className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
        >
          {showTable ? "Hide table view" : "Table view"}
        </button>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-100">
        <svg
          width={layout.width}
          height={layout.height}
          role="img"
          aria-label={`Lineage graph: ${graph.nodes.length} versions, ${graph.edges.length} edges. A table alternative is available below.`}
        >
          {/* edges under nodes */}
          {graph.edges.map((edge) => {
            const from = layout.positions.get(edge.parent_version_id);
            const to = layout.positions.get(edge.child_version_id);
            if (!from || !to) return null;
            const x1 = from.x + NODE_W;
            const y1 = from.y + NODE_H / 2;
            const x2 = to.x;
            const y2 = to.y + NODE_H / 2;
            const mx = (x1 + x2) / 2;
            return (
              <g key={edge.id}>
                <path
                  d={`M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`}
                  fill="none"
                  stroke="#64748b"
                  strokeWidth={1.5}
                />
                <polygon
                  points={`${x2},${y2} ${x2 - 7},${y2 - 4} ${x2 - 7},${y2 + 4}`}
                  fill="#64748b"
                />
                <title>{`${edge.transformation_name} (${edge.relationship_type})`}</title>
              </g>
            );
          })}
          {/* nodes */}
          {graph.nodes.map((node) => {
            const pos = layout.positions.get(node.version_id);
            if (!pos) return null;
            const selected = node.version_id === selectedVersionId;
            return (
              <g
                key={node.version_id}
                transform={`translate(${pos.x}, ${pos.y})`}
                onClick={() => onSelectVersion(node.version_id)}
                style={{ cursor: "pointer" }}
                role="button"
                aria-label={`${node.dataset_name} ${node.version_label}${node.invalidated ? " (invalidated)" : ""}, quality ${node.quality_status}`}
              >
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx={9}
                  fill={selected ? "rgba(59,130,246,0.16)" : "rgba(148,163,184,0.10)"}
                  stroke={selected ? "#3b82f6" : node.invalidated ? "#f87171" : "#475569"}
                  strokeWidth={selected ? 2 : 1.2}
                  strokeDasharray={node.invalidated ? "5 3" : undefined}
                />
                <circle cx={14} cy={NODE_H / 2} r={4.5} fill={QUALITY_COLOR[node.quality_status] ?? "#94a3b8"}>
                  <title>{`quality: ${node.quality_status}`}</title>
                </circle>
                <text x={26} y={19} fontSize={11} fontWeight={600} fill="currentColor">
                  {truncate(node.dataset_name, 22)}
                </text>
                <text x={26} y={35} fontSize={10} fill="#94a3b8">
                  {truncate(node.version_label, 14)}
                  {node.invalidated ? " · invalidated" : ""}
                  {node.direction === "self" ? " · selected" : ""}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {(showTable || parents.length + children.length > 0) && (
        <div className="grid gap-3 md:grid-cols-2">
          <LineageEdgeTable
            title="Parents (this version was derived from)"
            rows={parents.map((e) => ({ edge: e, node: byId.get(e.parent_version_id) }))}
            onSelect={onSelectVersion}
            pick="parent_version_id"
          />
          <LineageEdgeTable
            title="Children (derived from this version)"
            rows={children.map((e) => ({ edge: e, node: byId.get(e.child_version_id) }))}
            onSelect={onSelectVersion}
            pick="child_version_id"
          />
        </div>
      )}
    </div>
  );
}

function truncate(text: string, n: number): string {
  return text.length > n ? `${text.slice(0, n - 1)}…` : text;
}

function LineageEdgeTable({
  title,
  rows,
  onSelect,
  pick,
}: {
  title: string;
  rows: { edge: LineageGraph["edges"][number]; node: LineageNode | undefined }[];
  onSelect: (id: number) => void;
  pick: "parent_version_id" | "child_version_id";
}) {
  return (
    <div className="rounded-lg border border-slate-100 p-3">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h4>
      {rows.length === 0 ? (
        <p className="text-xs text-slate-400">None recorded.</p>
      ) : (
        <ul className="space-y-1.5">
          {rows.map(({ edge, node }) => (
            <li key={edge.id} className="text-sm">
              <button
                type="button"
                onClick={() => onSelect(edge[pick])}
                className="text-left font-medium text-blue-700 hover:underline"
              >
                {node ? `${node.dataset_name} · ${node.version_label}` : `version #${edge[pick]}`}
              </button>
              <span className="ml-1.5 text-xs text-slate-400">
                {edge.relationship_type} · {edge.transformation_name}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
