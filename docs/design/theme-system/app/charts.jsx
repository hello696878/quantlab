/* ============================================================================
   QuantLab — Chart library (hand-built SVG, no dependencies)
   All charts are responsive (viewBox + width:100%), animate on mount, and
   read CSS custom properties so they restyle with the active accent theme.
   Exposed on window: EquityChart, DrawdownChart, Sparkline, SweepHeatmap,
   WfBars, ScoreGauge, MiniArea.
   ============================================================================ */
const { useRef, useEffect, useState, useMemo } = React;

/* ---- helpers -------------------------------------------------------------- */
function niceScale(min, max) {
  if (min === max) { min -= 1; max += 1; }
  const pad = (max - min) * 0.08;
  return [min - pad, max + pad];
}
function path(points) { return points.map((p, i) => (i ? "L" : "M") + p[0].toFixed(2) + " " + p[1].toFixed(2)).join(" "); }
function useDrawn() {
  // Resolve to the FINAL (drawn) state synchronously so no chart reveal depends
  // on a CSS transition advancing — the preview document is often hidden, which
  // freezes transition timelines and would otherwise strand lines/bars/gauges at
  // their pre-animation (invisible) value. Real browsers still get count-ups,
  // panel rise, hover crosshairs, and live indicators for motion.
  const [on] = useState(true);
  return on;
}
function cssvar(name, fallback) {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

/* ============================================================================
   EquityChart — strategy vs benchmark line, gradient fill, hover crosshair
   ============================================================================ */
function EquityChart({ data, height = 300, showBenchmark = true, valueKey = "strategy" }) {
  const W = 1000, H = height, padL = 8, padR = 8, padT = 16, padB = 22;
  const drawn = useDrawn();
  const [hover, setHover] = useState(null);
  const wrapRef = useRef(null);

  const { sPath, bPath, areaPath, ys, xs, lo, hi } = useMemo(() => {
    const sVals = data.map((d) => d.strategy);
    const bVals = data.map((d) => d.benchmark);
    const all = showBenchmark ? sVals.concat(bVals) : sVals;
    const [lo, hi] = niceScale(Math.min(...all), Math.max(...all));
    const x = (i) => padL + (i / (data.length - 1)) * (W - padL - padR);
    const y = (v) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB);
    const sPts = data.map((d, i) => [x(i), y(d.strategy)]);
    const bPts = data.map((d, i) => [x(i), y(d.benchmark)]);
    const sPath = path(sPts), bPath = path(bPts);
    const areaPath = sPath + ` L ${x(data.length - 1)} ${H - padB} L ${x(0)} ${H - padB} Z`;
    return { sPath, bPath, areaPath, ys: sPts, xs: data.map((_, i) => x(i)), lo, hi };
  }, [data, height, showBenchmark]);

  function onMove(e) {
    const rect = wrapRef.current.getBoundingClientRect();
    const rel = (e.clientX - rect.left) / rect.width;
    const i = Math.max(0, Math.min(data.length - 1, Math.round(rel * (data.length - 1))));
    setHover(i);
  }
  const acc = cssvar("--accent", "#4d8bff");
  const accRgb = cssvar("--accent-rgb", "77,139,255");

  return (
    <div ref={wrapRef} style={{ position: "relative" }} onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" style={{ display: "block", overflow: "visible" }}>
        <defs>
          <linearGradient id="eqfill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={`rgba(${accRgb},0.28)`} />
            <stop offset="100%" stopColor={`rgba(${accRgb},0)`} />
          </linearGradient>
          <filter id="eqglow"><feGaussianBlur stdDeviation="3.2" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        {/* gridlines */}
        {[0, 0.25, 0.5, 0.75, 1].map((g) => (
          <line key={g} x1={padL} x2={W - padR} y1={padT + g * (H - padT - padB)} y2={padT + g * (H - padT - padB)}
            stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
        ))}
        <path d={areaPath} fill="url(#eqfill)" style={{ opacity: drawn ? 1 : 0, transition: "opacity .8s ease .5s" }} />
        {showBenchmark && (
          <path d={bPath} fill="none" stroke={cssvar("--accent-2", "#34e0e8")} strokeWidth="1.6" strokeDasharray="3 4"
            style={{ opacity: drawn ? 0.55 : 0, transition: "opacity .6s ease .4s" }} />
        )}
        <path d={sPath} fill="none" stroke={acc} strokeWidth="2.4" strokeLinejoin="round" filter="url(#eqglow)"
          pathLength="1" strokeDasharray="1" strokeDashoffset={drawn ? 0 : 1}
          style={{ transition: "stroke-dashoffset 1.3s cubic-bezier(.16,1,.3,1)" }} />
        {hover != null && (
          <g>
            <line x1={xs[hover]} x2={xs[hover]} y1={padT} y2={H - padB} stroke="rgba(255,255,255,0.18)" strokeWidth="1" />
            <circle cx={ys[hover][0]} cy={ys[hover][1]} r="4.5" fill={acc} stroke="#06080f" strokeWidth="2" />
          </g>
        )}
      </svg>
      {hover != null && (
        <div style={{ position: "absolute", top: 8, left: `clamp(8px, ${(xs[hover] / W) * 100}%, calc(100% - 168px))`,
          transform: "translateX(-50%)", pointerEvents: "none",
          background: "rgba(8,11,20,0.92)", border: "1px solid var(--line-strong)", borderRadius: 10, padding: "8px 11px",
          fontFamily: "var(--font-mono)", fontSize: 11.5, whiteSpace: "nowrap", backdropFilter: "blur(8px)" }}>
          <div style={{ color: "var(--text-mut)", marginBottom: 3 }}>{data[hover].date}</div>
          <div style={{ color: "var(--accent)" }}>STRAT ${(data[hover].strategy / 1000).toFixed(1)}k</div>
          {showBenchmark && <div style={{ color: "var(--text-mut)" }}>BENCH ${(data[hover].benchmark / 1000).toFixed(1)}k</div>}
        </div>
      )}
    </div>
  );
}

/* ============================================================================
   DrawdownChart — underwater area (always <= 0)
   ============================================================================ */
function DrawdownChart({ data, height = 150 }) {
  const W = 1000, H = height, padT = 10, padB = 18, padX = 8;
  const drawn = useDrawn();
  const { area, line, maxdd } = useMemo(() => {
    const vals = data.map((d) => d.dd);
    const lo = Math.min(...vals, -0.02);
    const x = (i) => padX + (i / (data.length - 1)) * (W - padX * 2);
    const y = (v) => padT + (v / lo) * (H - padT - padB);
    const pts = data.map((d, i) => [x(i), y(d.dd)]);
    const line = path(pts);
    const area = line + ` L ${x(data.length - 1)} ${padT} L ${x(0)} ${padT} Z`;
    return { area, line, maxdd: lo };
  }, [data, height]);
  const negRgb = "255,92,108";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" style={{ display: "block" }}>
      <defs>
        <linearGradient id="ddfill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={`rgba(${negRgb},0)`} />
          <stop offset="100%" stopColor={`rgba(${negRgb},0.32)`} />
        </linearGradient>
      </defs>
      <line x1={padX} x2={W - padX} y1={padT} y2={padT} stroke="rgba(255,255,255,0.08)" />
      <path d={area} fill="url(#ddfill)" style={{ opacity: drawn ? 1 : 0, transition: "opacity .9s ease .3s" }} />
      <path d={line} fill="none" stroke="var(--neg)" strokeWidth="1.8"
        pathLength="1" strokeDasharray="1" strokeDashoffset={drawn ? 0 : 1} style={{ transition: "stroke-dashoffset 1.2s var(--ease-out)" }} />
    </svg>
  );
}

/* ============================================================================
   Sparkline — tiny inline trend line
   ============================================================================ */
function Sparkline({ values, width = 120, height = 34, color }) {
  const drawn = useDrawn(700);
  const { d, up } = useMemo(() => {
    const lo = Math.min(...values), hi = Math.max(...values);
    const x = (i) => (i / (values.length - 1)) * width;
    const y = (v) => height - 3 - ((v - lo) / (hi - lo || 1)) * (height - 6);
    return { d: path(values.map((v, i) => [x(i), y(v)])), up: values[values.length - 1] >= values[0] };
  }, [values, width, height]);
  const c = color || (up ? "var(--pos)" : "var(--neg)");
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: "block" }}>
      <path d={d} fill="none" stroke={c} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round"
        pathLength="1" strokeDasharray="1" strokeDashoffset={drawn ? 0 : 1} style={{ transition: "stroke-dashoffset 1s var(--ease-out)" }} />
    </svg>
  );
}

/* ============================================================================
   SweepHeatmap — fast×slow grid colored by a chosen metric
   ============================================================================ */
function SweepHeatmap({ rows, fasts, slows, metric = "sharpe_ratio", best, onCell }) {
  const [hover, setHover] = useState(null);
  const vals = rows.map((r) => r[metric]);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const lookup = useMemo(() => {
    const m = {}; rows.forEach((r) => (m[r.fast_window + "x" + r.slow_window] = r)); return m;
  }, [rows]);
  // Heatmap ramp follows the ACTIVE accent: cold cells sit at the accent-2 hue,
  // hot cells at the primary accent hue, so the surface re-skins with the theme.
  const h1 = +cssvar("--accent-hue", "256"), h2 = +cssvar("--accent-2-hue", "205");
  function color(v) {
    if (v == null) return "transparent";
    const t = (v - lo) / (hi - lo || 1);
    const l = 0.27 + t * 0.42, c = 0.035 + t * 0.155, h = h2 + (h1 - h2) * t;
    return `oklch(${l} ${c} ${h})`;
  }
  return (
    <div style={{ overflowX: "auto" }}>
      <div style={{ display: "grid", gridTemplateColumns: `52px repeat(${slows.length}, 1fr)`, gap: 4, minWidth: 560 }}>
        <div />
        {slows.map((s) => <div key={s} className="mono" style={{ textAlign: "center", fontSize: 11, color: "var(--text-mut)", paddingBottom: 4 }}>{s}</div>)}
        {fasts.map((f) => (
          <React.Fragment key={f}>
            <div className="mono" style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", paddingRight: 8, fontSize: 11, color: "var(--text-mut)" }}>{f}</div>
            {slows.map((s) => {
              const r = lookup[f + "x" + s];
              const isBest = best && r && r.fast_window === best.fast_window && r.slow_window === best.slow_window;
              const hk = f + "x" + s;
              return (
                <div key={s}
                  onMouseEnter={() => setHover(hk)} onMouseLeave={() => setHover(null)}
                  onClick={() => r && onCell && onCell(r)}
                  style={{
                    aspectRatio: "1.6", borderRadius: 7, background: color(r ? r[metric] : null),
                    border: isBest ? "1.5px solid var(--accent-2)" : "1px solid var(--line-faint)",
                    boxShadow: isBest ? "0 0 16px -2px var(--accent-2)" : "none",
                    display: "flex", alignItems: "center", justifyContent: "center", cursor: r ? "pointer" : "default",
                    fontFamily: "var(--font-mono)", fontSize: 11, color: r && (r[metric] - lo) / (hi - lo) > 0.45 ? "#06080f" : "var(--text)",
                    position: "relative", transform: hover === hk ? "scale(1.08)" : "scale(1)", transition: "transform .15s var(--ease)", zIndex: hover === hk ? 2 : 1,
                  }}>
                  {r ? (metric === "sharpe_ratio" || metric === "calmar_ratio" ? r[metric].toFixed(2) : (r[metric] * 100).toFixed(0)) : ""}
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

/* ============================================================================
   WfBars — per-window train vs test Sharpe (paired bars)
   ============================================================================ */
function WfBars({ windows, height = 200 }) {
  const drawn = useDrawn(500);
  const maxV = Math.max(...windows.flatMap((w) => [w.train_metrics.sharpe_ratio, w.test_metrics.sharpe_ratio]), 1.5);
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 10, height, paddingTop: 8 }}>
      {windows.map((w, i) => (
        <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6, height: "100%" }}>
          <div style={{ flex: 1, display: "flex", alignItems: "flex-end", gap: 3, width: "100%", justifyContent: "center" }}>
            <div title={`Train ${w.train_metrics.sharpe_ratio}`} style={{ width: "42%", maxWidth: 16, borderRadius: "3px 3px 0 0",
              height: drawn ? `${(w.train_metrics.sharpe_ratio / maxV) * 100}%` : 0, background: "linear-gradient(var(--accent), color-mix(in oklch, var(--accent) 40%, transparent))",
              transition: `height .8s var(--ease-out) ${i * 50}ms` }} />
            <div title={`Test ${w.test_metrics.sharpe_ratio}`} style={{ width: "42%", maxWidth: 16, borderRadius: "3px 3px 0 0",
              height: drawn ? `${(Math.max(0, w.test_metrics.sharpe_ratio) / maxV) * 100}%` : 0,
              background: w.test_metrics.sharpe_ratio < 0.4 ? "var(--warn)" : "color-mix(in oklch, var(--accent-2) 78%, transparent)",
              transition: `height .8s var(--ease-out) ${i * 50 + 60}ms` }} />
          </div>
          <div className="mono" style={{ fontSize: 9.5, color: "var(--text-faint)" }}>{w.window_index}</div>
        </div>
      ))}
    </div>
  );
}

/* ============================================================================
   ScoreGauge — radial overfitting risk score 0..100
   ============================================================================ */
function ScoreGauge({ score, band, size = 132 }) {
  const drawn = useDrawn(400);
  const r = size / 2 - 10, c = 2 * Math.PI * r, cx = size / 2, cy = size / 2;
  const frac = score / 100;
  const col = band === "high" ? "var(--neg)" : band === "moderate" ? "var(--warn)" : "var(--pos)";
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="9" />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={col} strokeWidth="9" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={drawn ? c * (1 - frac) : c}
          style={{ transition: "stroke-dashoffset 1.2s var(--ease-out)", filter: `drop-shadow(0 0 6px ${col})` }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <div className="mono" style={{ fontSize: 30, fontWeight: 700, color: col, lineHeight: 1 }}>{drawn ? score : 0}</div>
        <div className="uplabel" style={{ marginTop: 4, color: col }}>{band} risk</div>
      </div>
    </div>
  );
}

/* ---- expose --------------------------------------------------------------- */
Object.assign(window, { EquityChart, DrawdownChart, Sparkline, SweepHeatmap, WfBars, ScoreGauge });
