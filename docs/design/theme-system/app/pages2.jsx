/* ============================================================================
   QuantLab — Pages part 2: Research · Comparison · Sweep · Walk-Forward ·
   Design Tokens · App router
   ============================================================================ */
const { useState: useS2, useMemo: useM2 } = React;

/* ---- small multi-line overlay (normalized to 100) ------------------------- */
function MultiEquity({ series, height = 300 }) {
  const W = 1000, padL = 8, padR = 8, padT = 16, padB = 20;
  // start drawn=true: the stroke-dashoffset transition can't advance in a hidden
  // preview document, so initialize at the final (drawn) state to stay visible.
  const drawn = true;
  const norm = series.map((s) => ({ ...s, vals: s.curve.map((p) => (p.strategy / s.curve[0].strategy) * 100) }));
  const all = norm.flatMap((s) => s.vals);
  const lo = Math.min(...all) * 0.98, hi = Math.max(...all) * 1.02;
  const n = norm[0].vals.length;
  const x = (i) => padL + (i / (n - 1)) * (W - padL - padR);
  const y = (v) => padT + (1 - (v - lo) / (hi - lo)) * (height - padT - padB);
  return (
    <svg viewBox={`0 0 ${W} ${height}`} width="100%" height={height} preserveAspectRatio="none" style={{ display: "block" }}>
      {[0, 0.5, 1].map((g) => <line key={g} x1={padL} x2={W - padR} y1={padT + g * (height - padT - padB)} y2={padT + g * (height - padT - padB)} stroke="rgba(255,255,255,0.05)" />)}
      {norm.map((s, idx) => {
        const d = s.vals.map((v, i) => (i ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1)).join(" ");
        return <path key={s.id} d={d} fill="none" stroke={s.color} strokeWidth={s.bench ? 1.6 : 2.2} strokeDasharray={s.bench ? "3 4" : "1"}
          pathLength="1" strokeDashoffset={drawn ? 0 : 1} style={{ transition: `stroke-dashoffset 1.2s var(--ease-out) ${idx * 80}ms`, opacity: s.bench ? 0.6 : 1, filter: s.bench ? "none" : "drop-shadow(0 0 4px " + s.color + "44)" }} />;
      })}
    </svg>
  );
}

/* ============================================================================
   RESEARCH TOOLS WORKSPACE  (train/test validation as the hero tool)
   ============================================================================ */
function ResearchPage() {
  const tt = QL.TRAINTEST;
  const deg = [
    { label: "Sharpe", is: tt.in_sample_metrics.sharpe_ratio, oos: tt.out_of_sample_metrics.sharpe_ratio, d: tt.sharpe_degradation, fmt: (x) => x.toFixed(2) },
    { label: "CAGR", is: tt.in_sample_metrics.cagr, oos: tt.out_of_sample_metrics.cagr, d: tt.cagr_degradation, fmt: (x) => fmt.pctRaw(x, 1) },
    { label: "Calmar", is: tt.in_sample_metrics.calmar_ratio, oos: tt.out_of_sample_metrics.calmar_ratio, d: tt.calmar_degradation, fmt: (x) => x.toFixed(2) },
    { label: "Max DD", is: tt.in_sample_metrics.max_drawdown, oos: tt.out_of_sample_metrics.max_drawdown, d: -tt.max_drawdown_worsening, fmt: (x) => fmt.pctRaw(x, 1) },
  ];
  const tools = [
    { id: "sweep", title: "Parameter Sweep", desc: "Scan a fast×slow grid to find robust regions, not overfit spikes.", icon: "sweep" },
    { id: "walkfwd", title: "Walk-Forward", desc: "Roll the optimization window forward for realistic OOS equity.", icon: "walkfwd" },
    { id: "compare", title: "Strategy Comparison", desc: "Rank 5 strategies side-by-side on the same asset.", icon: "compare" },
  ];
  return (
    <div style={{ padding: 28, display: "flex", flexDirection: "column", gap: 18 }}>
      {/* tool launcher */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
        {tools.map((t) => (
          <button key={t.id} onClick={() => window.__qlnav(t.id)} className="glass sheen rise"
            style={{ textAlign: "left", padding: 18, cursor: "pointer", border: "1px solid var(--line)", display: "flex", flexDirection: "column", gap: 10, transition: "all .18s var(--ease)" }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "color-mix(in oklch, var(--accent) 40%, transparent)"; e.currentTarget.style.transform = "translateY(-3px)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--line)"; e.currentTarget.style.transform = "none"; }}>
            <span style={{ width: 36, height: 36, borderRadius: 10, background: "rgba(var(--accent-rgb),0.13)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center" }}><Icon name={t.icon} size={20} /></span>
            <div style={{ fontSize: 14.5, fontWeight: 700, color: "var(--text-hi)" }}>{t.title}</div>
            <div style={{ fontSize: 12.5, color: "var(--text-mut)", lineHeight: 1.5 }}>{t.desc}</div>
            <span className="accent" style={{ fontSize: 12, fontWeight: 600, marginTop: 2 }}>Open tool →</span>
          </button>
        ))}
      </div>

      {/* Train/Test validation hero */}
      <Panel title="Train / Test Out-of-Sample Validation · SPY" accent
        right={<Badge tone="warn" solid>OOS COLLAPSED</Badge>}>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 340px", gap: 20 }}>
          <div>
            <div style={{ display: "flex", gap: 8, marginBottom: 14, fontSize: 12, color: "var(--text-mut)" }} className="mono">
              <span>IS 2015→2021 ({tt.in_sample_days}d)</span><span style={{ color: "var(--text-faint)" }}>│</span><span>OOS 2021→2023 ({tt.out_of_sample_days}d)</span>
              <span style={{ marginLeft: "auto", color: "var(--accent)" }}>best: SMA {tt.best_fast_window}/{tt.best_slow_window}</span>
            </div>
            <MultiEquity height={236} series={[
              { id: "oos", color: "var(--accent)", curve: tt.oos_curve },
              { id: "bench", color: "var(--text-faint)", bench: true, curve: tt.oos_curve.map((p) => ({ strategy: p.benchmark })) },
            ]} />
            <p style={{ margin: "10px 0 0", fontSize: 11.5, color: "var(--text-faint)" }}>Out-of-sample equity from parameters selected on in-sample data only.</p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
              <thead><tr>{["Metric", "IS", "OOS", "Δ"].map((h, i) => <th key={h} className="uplabel" style={{ padding: "0 0 9px", textAlign: i ? "right" : "left", fontWeight: 600 }}>{h}</th>)}</tr></thead>
              <tbody className="mono">
                {deg.map((r) => (
                  <tr key={r.label} style={{ borderTop: "1px solid var(--line-faint)" }}>
                    <td style={{ padding: "9px 0", color: "var(--text)", fontFamily: "var(--font-ui)" }}>{r.label}</td>
                    <td style={{ padding: "9px 0", textAlign: "right", color: "var(--text-hi)" }}>{r.fmt(r.is)}</td>
                    <td style={{ padding: "9px 0", textAlign: "right", color: "var(--text-hi)" }}>{r.fmt(r.oos)}</td>
                    <td style={{ padding: "9px 0", textAlign: "right", color: r.d < 0 ? "var(--neg)" : "var(--pos)", fontWeight: 600 }}>{r.d >= 0 ? "+" : ""}{r.fmt(r.d)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div style={{ marginTop: 16 }}>
          <AlertCard tone="neg" title="Out-of-sample performance collapsed">
            OOS Sharpe fell to <b className="mono">0.61</b> from an in-sample <b className="mono">1.42</b> — a <b className="mono">57%</b> decay, and below the buy-and-hold benchmark Sharpe of <b className="mono">0.74</b>. The selected SMA 30/130 parameters were likely overfit to the 2015–2021 regime. Prefer parameters from a robust sweep plateau and confirm with walk-forward.
          </AlertCard>
        </div>
      </Panel>
    </div>
  );
}

/* ============================================================================
   STRATEGY COMPARISON
   ============================================================================ */
function ComparePage() {
  const palette = ["var(--accent)", "var(--cyan)", "var(--emerald)", "var(--warn)", "oklch(0.72 0.15 320)"];
  const strat = QL.STRATEGIES.filter((s) => s.id !== "pairs").map((s, i) => ({ ...QL.BUILT[s.id], color: palette[i] }));
  const series = strat.map((s) => ({ id: s.id, color: s.color, curve: s.equity_curve }))
    .concat([{ id: "bench", color: "var(--text-faint)", bench: true, curve: strat[0].equity_curve.map((p) => ({ strategy: p.benchmark })) }]);
  const bySharpe = [...strat].sort((a, b) => b.strategy_metrics.sharpe_ratio - a.strategy_metrics.sharpe_ratio)[0];
  const byRet = [...strat].sort((a, b) => b.strategy_metrics.total_return - a.strategy_metrics.total_return)[0];
  const byDD = [...strat].sort((a, b) => b.strategy_metrics.max_drawdown - a.strategy_metrics.max_drawdown)[0];
  const byCalmar = [...strat].sort((a, b) => b.strategy_metrics.calmar_ratio - a.strategy_metrics.calmar_ratio)[0];
  const ranks = [
    { label: "Best Sharpe", win: bySharpe, v: bySharpe.strategy_metrics.sharpe_ratio.toFixed(2) },
    { label: "Top Return", win: byRet, v: fmt.pct(byRet.strategy_metrics.total_return, 0) },
    { label: "Best Calmar", win: byCalmar, v: byCalmar.strategy_metrics.calmar_ratio.toFixed(2) },
    { label: "Lowest Drawdown", win: byDD, v: fmt.pct(byDD.strategy_metrics.max_drawdown, 0) },
  ];
  return (
    <div style={{ padding: 28, display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 14 }}>
        {ranks.map((r, i) => (
          <div key={r.label} className="glass sheen rise" style={{ padding: "15px 16px", animationDelay: i * 60 + "ms", borderColor: i === 0 ? "color-mix(in oklch, var(--accent) 30%, var(--line))" : undefined }}>
            <div className="uplabel" style={{ marginBottom: 8 }}>{r.label}</div>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: r.win.color }} />
              <span style={{ fontSize: 14, fontWeight: 700, color: "var(--text-hi)" }}>{r.win.short}</span>
              <span className="mono" style={{ marginLeft: "auto", fontSize: 15, fontWeight: 700, color: r.win.color }}>{r.v}</span>
            </div>
          </div>
        ))}
      </div>
      <Panel title="Equity Curves — 5 strategies on SPY (normalized to 100)" accent
        right={<div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>{strat.map((s) => (
          <span key={s.id} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-mut)" }}><span style={{ width: 10, height: 10, borderRadius: 3, background: s.color }} />{s.short}</span>
        ))}</div>}>
        <MultiEquity series={series} height={300} />
      </Panel>
      <Panel title="Side-by-side metrics">
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5, minWidth: 640 }}>
            <thead><tr>{["Strategy", "Ticker", "Return", "CAGR", "Sharpe", "Sortino", "Max DD", "Calmar", "Trades"].map((h, i) => (
              <th key={h} className="uplabel" style={{ padding: "0 0 12px", textAlign: i >= 2 ? "right" : "left", fontWeight: 600 }}>{h}</th>))}</tr></thead>
            <tbody className="mono">
              {strat.map((s) => (
                <tr key={s.id} style={{ borderTop: "1px solid var(--line-faint)" }}>
                  <td style={{ padding: "10px 0", fontFamily: "var(--font-ui)" }}><span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: s.color }} /><b style={{ color: "var(--text-hi)" }}>{s.name}</b></span></td>
                  <td style={{ color: "var(--text-mut)" }}>{s.ticker}</td>
                  <td style={{ textAlign: "right", color: s.strategy_metrics.total_return >= 0 ? "var(--pos)" : "var(--neg)", fontWeight: 600 }}>{fmt.pct(s.strategy_metrics.total_return, 0)}</td>
                  <td style={{ textAlign: "right", color: "var(--text)" }}>{fmt.pctRaw(s.strategy_metrics.cagr, 1)}</td>
                  <td style={{ textAlign: "right", color: "var(--text-hi)", fontWeight: 600 }}>{s.strategy_metrics.sharpe_ratio.toFixed(2)}</td>
                  <td style={{ textAlign: "right", color: "var(--text)" }}>{s.strategy_metrics.sortino_ratio.toFixed(2)}</td>
                  <td style={{ textAlign: "right", color: "var(--neg)" }}>{fmt.pct(s.strategy_metrics.max_drawdown, 0)}</td>
                  <td style={{ textAlign: "right", color: "var(--text)" }}>{s.strategy_metrics.calmar_ratio.toFixed(2)}</td>
                  <td style={{ textAlign: "right", color: "var(--text-mut)" }}>{s.num_trades}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

/* ============================================================================
   PARAMETER SWEEP HEATMAP
   ============================================================================ */
function SweepPage() {
  const [metric, setMetric] = useS2("sharpe_ratio");
  const [cell, setCell] = useS2(QL.SWEEP_BEST);
  const metrics = [{ id: "sharpe_ratio", label: "Sharpe" }, { id: "cagr", label: "CAGR %" }, { id: "calmar_ratio", label: "Calmar" }, { id: "max_drawdown", label: "Max DD %" }];
  const vals = QL.SWEEP.map((r) => r.sharpe_ratio);
  const dispersion = (Math.max(...vals) - Math.min(...vals)).toFixed(2);
  return (
    <div style={{ padding: 28, display: "grid", gridTemplateColumns: "minmax(0, 1fr) 320px", gap: 18, alignItems: "start" }}>
      <Panel title="SMA Crossover Sweep · SPY · fast × slow" accent
        right={<div style={{ display: "flex", gap: 4, padding: 3, background: "var(--glass)", borderRadius: 9 }}>
          {metrics.map((m) => (
            <button key={m.id} onClick={() => setMetric(m.id)} className="mono" style={{ padding: "5px 10px", borderRadius: 7, border: "none", cursor: "pointer", fontSize: 11, fontWeight: 600,
              background: metric === m.id ? "rgba(var(--accent-rgb),0.18)" : "transparent", color: metric === m.id ? "var(--accent)" : "var(--text-mut)" }}>{m.label}</button>
          ))}
        </div>}>
        <SweepHeatmap rows={QL.SWEEP} fasts={QL.FAST} slows={QL.SLOW} metric={metric} best={QL.SWEEP_BEST} onCell={setCell} />
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 16, fontSize: 11.5, color: "var(--text-mut)" }}>
          <span>fast window (rows) · slow window (cols)</span>
          <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>low
            <span style={{ width: 120, height: 8, borderRadius: 999, background: "linear-gradient(90deg, oklch(0.28 0.04 256), oklch(0.68 0.2 160))" }} />high</span>
        </div>
      </Panel>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Panel title="Best parameters" accent>
          <div className="mono" style={{ fontSize: 22, fontWeight: 700, color: "var(--accent)" }}>SMA {QL.SWEEP_BEST.fast_window}/{QL.SWEEP_BEST.slow_window}</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 14 }}>
            {[["Sharpe", QL.SWEEP_BEST.sharpe_ratio.toFixed(2)], ["CAGR", fmt.pctRaw(QL.SWEEP_BEST.cagr, 1)], ["Max DD", fmt.pctRaw(QL.SWEEP_BEST.max_drawdown, 1)], ["Calmar", QL.SWEEP_BEST.calmar_ratio.toFixed(2)]].map(([k, v]) => (
              <div key={k} className="glass" style={{ padding: "9px 11px", borderRadius: 9 }}>
                <div className="uplabel" style={{ fontSize: 9.5 }}>{k}</div>
                <div className="mono" style={{ fontSize: 15, fontWeight: 700, color: "var(--text-hi)", marginTop: 3 }}>{v}</div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title={`Selected cell · SMA ${cell.fast_window}/${cell.slow_window}`}>
          <table style={{ width: "100%", fontSize: 12.5 }}><tbody className="mono">
            {[["Sharpe", cell.sharpe_ratio.toFixed(2)], ["CAGR", fmt.pctRaw(cell.cagr, 1)], ["Total return", fmt.pctRaw(cell.total_return, 0)], ["Max drawdown", fmt.pctRaw(cell.max_drawdown, 1)], ["Trades", cell.num_trades]].map(([k, v]) => (
              <tr key={k}><td style={{ padding: "5px 0", color: "var(--text-mut)", fontFamily: "var(--font-ui)" }}>{k}</td><td style={{ padding: "5px 0", textAlign: "right", color: "var(--text-hi)" }}>{v}</td></tr>
            ))}
          </tbody></table>
        </Panel>
        <AlertCard tone="warn" title="Watch for overfit spikes">
          Sharpe ranges <b className="mono">{dispersion}</b> across the grid. Isolated high cells surrounded by weak neighbours are red flags — trust broad <b>plateaus</b>, not lone peaks.
        </AlertCard>
      </div>
    </div>
  );
}

/* ============================================================================
   WALK-FORWARD OPTIMIZATION
   ============================================================================ */
function WalkForwardPage() {
  const wf = QL.WALKFWD;
  const of = QL.overfittingScore({ degradation: 0.52, instability: wf.parameter_stability.parameters_unstable ? 0.75 : 0.3, dispersion: 0.4, ddWorsen: 0.35 });
  const ps = wf.parameter_stability;
  return (
    <div style={{ padding: 28, display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 300px", gap: 14, alignItems: "stretch" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14, minWidth: 0 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 14 }}>
            <MetricCard label="Aggregate OOS Return" value={wf.aggregate_metrics.total_return} format="pct" decimals={1} deltaTone="pos" delta={fmt.pctRaw(wf.aggregate_metrics.cagr, 1) + " CAGR"} accent delay={0} />
            <MetricCard label="Stitched Sharpe" value={wf.aggregate_metrics.sharpe_ratio} format="num" decimals={2} deltaTone={wf.aggregate_metrics.sharpe_ratio >= 1 ? "pos" : "warn"} delta={`${wf.num_windows} folds`} delay={80} />
            <MetricCard label="Max Drawdown" value={wf.aggregate_metrics.max_drawdown} format="pct" decimals={1} deltaTone="neg" delta="across folds" delay={160} />
          </div>
          <Panel title="Stitched OOS Equity" accent
            right={<span className="mono" style={{ fontSize: 11, color: "var(--text-mut)" }}>train 504d · test 126d · step 126d</span>}>
            <EquityChart data={wf.stitched_equity_curve} height={206} />
          </Panel>
        </div>
        <Panel title="Overfitting Risk" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }} accent={of.band !== "low"}>
          <ScoreGauge score={of.score} band={of.band} size={120} />
          <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: 9 }}>
            {of.factors.map((f) => (
              <div key={f.label}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 10.5, color: "var(--text-mut)", marginBottom: 4 }}><span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.label}</span><span className="mono" style={{ flexShrink: 0 }}>{Math.round(f.value * 100)}</span></div>
                <div style={{ height: 4, borderRadius: 999, background: "var(--glass-strong)" }}><div style={{ width: f.value * 100 + "%", height: "100%", borderRadius: 999, background: f.value > 0.6 ? "var(--neg)" : f.value > 0.4 ? "var(--warn)" : "var(--pos)" }} /></div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <Panel title="Train vs Test Sharpe — per window"
          right={<div style={{ display: "flex", gap: 12, fontSize: 11, color: "var(--text-mut)" }}><span style={{ display: "flex", alignItems: "center", gap: 5 }}><span style={{ width: 9, height: 9, borderRadius: 2, background: "var(--accent)" }} />Train</span><span style={{ display: "flex", alignItems: "center", gap: 5 }}><span style={{ width: 9, height: 9, borderRadius: 2, background: "var(--cyan)" }} />Test</span></div>}>
          <WfBars windows={wf.windows} height={200} />
          <p style={{ margin: "10px 0 0", fontSize: 11.5, color: "var(--text-faint)" }}>Test Sharpe sits well below train in most folds — the gap quantifies optimization bias.</p>
        </Panel>
        <Panel title="Parameter Stability" accent={ps.parameters_unstable}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 14 }}>
            <div><div className="mono" style={{ fontSize: 26, fontWeight: 700, color: ps.parameters_unstable ? "var(--warn)" : "var(--pos)" }}>{ps.unique_parameter_sets}/{ps.num_windows}</div><div className="uplabel">unique param sets</div></div>
            <div style={{ flex: 1 }}>
              {ps.parameters_unstable
                ? <AlertCard tone="warn" title="Parameters are unstable">The optimizer jumps between {ps.unique_parameter_sets} different SMA pairs across {ps.num_windows} windows. A robust strategy should re-select similar parameters; frequent switching suggests it's chasing noise.</AlertCard>
                : <AlertCard tone="pos" title="Parameters are stable" icon="shield">The optimizer converges on consistent parameters across windows — a sign of genuine signal.</AlertCard>}
            </div>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {wf.windows.map((w) => (
              <span key={w.window_index} className="mono" style={{ fontSize: 10.5, padding: "4px 8px", borderRadius: 7, background: (w.best_fast_window === ps.most_common_fast_window && w.best_slow_window === ps.most_common_slow_window) ? "rgba(var(--accent-rgb),0.16)" : "var(--glass)", color: (w.best_fast_window === ps.most_common_fast_window && w.best_slow_window === ps.most_common_slow_window) ? "var(--accent)" : "var(--text-mut)", border: "1px solid var(--line)" }}>{w.best_fast_window}/{w.best_slow_window}</span>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}

Object.assign(window, { MultiEquity, ResearchPage, ComparePage, SweepPage, WalkForwardPage });
