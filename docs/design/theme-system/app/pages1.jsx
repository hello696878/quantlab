/* ============================================================================
   QuantLab — Pages part 1:  Dashboard + Backtest workspace
   ============================================================================ */
const { useState: useS1, useEffect: useE1, useMemo: useM1 } = React;

/* ---- shared: render the 8 standard performance metrics as a grid ---------- */
function MetricsStrip({ m, bench, label }) {
  const cards = [
    { label: "Total Return", value: m.total_return, format: "pct", decimals: 1, tone: m.total_return >= 0 ? "pos" : "neg", accent: true },
    { label: "CAGR", value: m.cagr, format: "pct", decimals: 1, tone: m.cagr >= 0 ? "pos" : "neg" },
    { label: "Sharpe", value: m.sharpe_ratio, format: "num", decimals: 2, tone: m.sharpe_ratio >= 1 ? "pos" : "warn" },
    { label: "Sortino", value: m.sortino_ratio, format: "num", decimals: 2 },
    { label: "Max Drawdown", value: m.max_drawdown, format: "pct", decimals: 1, tone: "neg" },
    { label: "Volatility", value: m.volatility, format: "pctRaw", decimals: 1 },
    { label: "Calmar", value: m.calmar_ratio, format: "num", decimals: 2 },
    { label: "Win Rate", value: m.win_rate, format: "pctRaw", decimals: 1 },
  ];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(158px, 1fr))", gap: 12 }}>
      {cards.map((c, i) => (
        <MetricCard key={c.label} label={c.label} value={c.value} format={c.format} decimals={c.decimals}
          deltaTone={c.tone} accent={c.accent} delay={i * 50} />
      ))}
    </div>
  );
}

/* ============================================================================
   DASHBOARD
   ============================================================================ */
function DashboardPage() {
  const P = QL.PORTFOLIO;
  const of = QL.overfittingScore();
  const strat = QL.STRATEGIES.map((s) => QL.BUILT[s.id]);
  return (
    <div style={{ padding: 28, display: "flex", flexDirection: "column", gap: 18 }}>
      {/* hero metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14 }}>
        <MetricCard label="Portfolio NAV" value={P.nav} format="money" accent delta="LIVE" deltaTone="pos" sub="6 active strategies · $100k start" delay={0} />
        <MetricCard label="Aggregate Return" value={P.metrics.total_return} format="pct" decimals={1} deltaTone="pos" delta={fmt.pctRaw(P.metrics.cagr, 1) + " CAGR"} sub="net of 10 bps costs" delay={80} />
        <MetricCard label="Blended Sharpe" value={P.metrics.sharpe_ratio} format="num" decimals={2} deltaTone={P.metrics.sharpe_ratio >= 1 ? "pos" : "warn"} delta="risk-adj" sub="vs 0.73 benchmark" delay={160} />
        <MetricCard label="Max Drawdown" value={P.metrics.max_drawdown} format="pct" decimals={1} deltaTone="neg" delta="peak→trough" sub={"Calmar " + P.metrics.calmar_ratio.toFixed(2)} delay={240} />
      </div>

      {/* equity + risk */}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 320px", gap: 14 }}>
        <Panel title="Portfolio Equity — blended (2015–2023)" accent
          right={<div style={{ display: "flex", gap: 14, alignItems: "center" }}>
            <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-mut)" }}><span style={{ width: 14, height: 2, background: "var(--accent)", borderRadius: 2 }} />Strategy</span>
            <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-mut)" }}><span style={{ width: 14, height: 0, borderTop: "2px dashed var(--text-faint)" }} />Benchmark</span>
          </div>}>
          <EquityChart data={P.equity_curve} height={264} />
        </Panel>
        <Panel title="Overfitting Risk" accent={of.band !== "low"} style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14, flex: 1, justifyContent: "center" }}>
            <ScoreGauge score={of.score} band={of.band} />
            <p style={{ margin: 0, fontSize: 12, color: "var(--text-mut)", textAlign: "center", lineHeight: 1.5 }}>
              Composite across walk-forward decay, parameter stability & sweep dispersion.
            </p>
            <button onClick={() => window.__qlnav && window.__qlnav("walkfwd")} style={{ width: "100%", padding: "9px", borderRadius: 10, border: "1px solid var(--line-strong)", background: "var(--glass)", color: "var(--text-hi)", fontSize: 12.5, fontWeight: 600, cursor: "pointer" }}>
              View diagnostics →
            </button>
          </div>
        </Panel>
      </div>

      {/* watchlist + activity */}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 340px", gap: 14 }}>
        <Panel title="Strategy Watchlist" right={<Badge tone="cyan">{strat.length} active</Badge>}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead><tr>
              {["Strategy", "Ticker", "", "Return", "Sharpe", "Max DD"].map((h, i) => (
                <th key={i} className="uplabel" style={{ padding: "0 0 12px", textAlign: i >= 3 ? "right" : "left", fontWeight: 600 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {strat.map((s) => (
                <tr key={s.id} style={{ borderTop: "1px solid var(--line-faint)", cursor: "pointer" }}
                  onClick={() => window.__qlnav && window.__qlnav("backtest", s.id)}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--glass)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                  <td style={{ padding: "11px 0" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ width: 26, height: 26, borderRadius: 7, background: "var(--glass-strong)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-mono)", fontSize: 9, fontWeight: 700 }}>{s.short}</span>
                      <span style={{ fontWeight: 600, color: "var(--text-hi)" }}>{s.name}</span>
                    </div>
                  </td>
                  <td className="mono" style={{ color: "var(--text-mut)", fontSize: 12 }}>{s.ticker}</td>
                  <td style={{ padding: "0 8px" }}><Sparkline values={s.spark} width={88} height={26} /></td>
                  <td className="mono" style={{ textAlign: "right", color: s.strategy_metrics.total_return >= 0 ? "var(--pos)" : "var(--neg)", fontWeight: 600 }}>{fmt.pct(s.strategy_metrics.total_return, 0)}</td>
                  <td className="mono" style={{ textAlign: "right", color: "var(--text-hi)" }}>{s.strategy_metrics.sharpe_ratio.toFixed(2)}</td>
                  <td className="mono" style={{ textAlign: "right", color: "var(--neg)" }}>{fmt.pct(s.strategy_metrics.max_drawdown, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <Panel title="Activity">
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {QL.ACTIVITY.map((a, i) => {
              const tone = { accent: "var(--accent)", pos: "var(--pos)", warn: "var(--warn)", mut: "var(--text-mut)" }[a.tone];
              return (
                <div key={i} style={{ display: "flex", gap: 11, padding: "10px 0", borderTop: i ? "1px solid var(--line-faint)" : "none" }}>
                  <span style={{ width: 7, height: 7, borderRadius: 999, background: tone, marginTop: 6, flexShrink: 0, boxShadow: `0 0 6px ${tone}` }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12.5, color: "var(--text)", lineHeight: 1.4 }}><span style={{ color: "var(--text-faint)" }}>{a.who}</span> {a.what}</div>
                    <div className="mono" style={{ fontSize: 10, color: "var(--text-faint)", marginTop: 2 }}>{a.t} ago · {a.tag}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>
      </div>
    </div>
  );
}

/* ============================================================================
   BACKTEST WORKSPACE
   ============================================================================ */
const PARAM_CONFIG = {
  sma_crossover: [{ k: "fast", label: "Fast SMA window", min: 5, max: 80, def: 50 }, { k: "slow", label: "Slow SMA window", min: 60, max: 300, def: 200 }],
  momentum: [{ k: "win", label: "Lookback window (days)", min: 20, max: 252, def: 126 }, { k: "entry", label: "Entry threshold", min: -0.1, max: 0.1, step: 0.01, def: 0 }],
  rsi_mean_reversion: [{ k: "win", label: "RSI window", min: 5, max: 30, def: 14 }, { k: "os", label: "Oversold threshold", min: 10, max: 45, def: 30 }, { k: "ex", label: "Exit threshold", min: 45, max: 80, def: 50 }],
  bollinger_band: [{ k: "win", label: "BB window", min: 10, max: 50, def: 20 }, { k: "std", label: "Num. std-dev (σ)", min: 1, max: 3.5, step: 0.1, def: 2 }],
  volatility_breakout: [{ k: "win", label: "Lookback window", min: 5, max: 60, def: 20 }, { k: "mult", label: "Breakout multiplier", min: 0.2, max: 3, step: 0.1, def: 1 }],
  pairs: [{ k: "win", label: "Z-score lookback", min: 20, max: 120, def: 60 }, { k: "entry", label: "Entry |z|", min: 1, max: 3.5, step: 0.1, def: 2 }, { k: "exit", label: "Exit z", min: 0.1, max: 1.5, step: 0.1, def: 0.5 }],
};

function BacktestPage({ initialStrategy }) {
  const [strategy, setStrategy] = useS1(initialStrategy || "sma_crossover");
  const [cost, setCost] = useS1(10);
  const [params, setParams] = useS1({});
  const [loading, setLoading] = useS1(false);
  const [result, setResult] = useS1(QL.BUILT[initialStrategy || "sma_crossover"]);

  useE1(() => {
    const cfg = PARAM_CONFIG[strategy] || [];
    const init = {}; cfg.forEach((c) => (init[c.k] = c.def)); setParams(init);
  }, [strategy]);

  function run() {
    setLoading(true); setResult(null);
    setTimeout(() => { setResult(QL.BUILT[strategy]); setLoading(false); }, 950);
  }
  const cfg = PARAM_CONFIG[strategy] || [];
  const sel = QL.STRATEGIES.find((s) => s.id === strategy);

  return (
    <div style={{ padding: 28, display: "grid", gridTemplateColumns: "300px minmax(0, 1fr)", gap: 18, alignItems: "start" }}>
      {/* control rail */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14, position: "sticky", top: 100 }}>
        <Panel title="Strategy">
          <StrategySelector value={strategy} onChange={setStrategy} options={QL.STRATEGIES} />
          <p style={{ margin: "12px 0 0", fontSize: 12, color: "var(--text-mut)", lineHeight: 1.55 }}>{sel.desc}</p>
        </Panel>
        <Panel title="Universe">
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <Field label="Ticker" value={sel.ticker} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <Field label="Start" value="2015-01-01" small />
              <Field label="End" value="2023-12-31" small />
            </div>
          </div>
        </Panel>
        <Panel title="Parameters">
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {cfg.map((c) => (
              <ParamSlider key={c.k} label={c.label} value={params[c.k] ?? c.def} min={c.min} max={c.max} step={c.step || 1}
                onChange={(v) => setParams((p) => ({ ...p, [c.k]: v }))} />
            ))}
            <ParamSlider label="Transaction cost" value={cost} min={0} max={50} step={1} unit=" bps" onChange={setCost} />
          </div>
        </Panel>
        <RunButton loading={loading} onClick={run} />
      </div>

      {/* results */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14, minWidth: 0 }}>
        {loading ? <BacktestSkeleton /> : result && (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <h2 style={{ margin: 0, fontSize: 17, color: "var(--text-hi)" }}>{result.ticker}</h2>
              <Badge tone="accent">{result.name}</Badge>
              <span className="mono" style={{ fontSize: 11.5, color: "var(--text-mut)" }}>{result.params} · {cost} bps · {result.num_trades} trades</span>
              <button style={{ marginLeft: "auto", padding: "6px 13px", borderRadius: 9, border: "1px solid var(--line-strong)", background: "var(--glass)", color: "var(--text-hi)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Save backtest</button>
            </div>
            <MetricsStrip m={result.strategy_metrics} bench={result.benchmark_metrics} />
            <Panel title="Equity Curve — strategy vs buy & hold" accent
              right={<div style={{ display: "flex", gap: 14 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-mut)" }}><span style={{ width: 14, height: 2, background: "var(--accent)" }} />Strategy</span>
                <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-mut)" }}><span style={{ width: 14, borderTop: "2px dashed var(--text-faint)" }} />Benchmark</span>
              </div>}>
              <EquityChart data={result.equity_curve} height={300} />
            </Panel>
            <Panel title="Drawdown — underwater curve">
              <DrawdownChart data={result.drawdown} height={150} />
            </Panel>
            <Panel title={`Trade Log · ${result.num_trades} events`}>
              <TradeTable trades={result.trades} />
            </Panel>
          </>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, small }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      <span className="uplabel">{label}</span>
      <div className="mono glass" style={{ padding: small ? "7px 9px" : "9px 11px", borderRadius: 9, fontSize: small ? 12 : 13, color: "var(--text-hi)" }}>{value}</div>
    </div>
  );
}

function BacktestSkeleton() {
  const shimmer = { background: "linear-gradient(90deg, var(--glass) 25%, var(--glass-strong) 37%, var(--glass) 63%)", backgroundSize: "200% 100%", animation: "shimmer 1.3s infinite", borderRadius: 12 };
  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>{[0, 1, 2, 3].map((i) => <div key={i} style={{ ...shimmer, height: 104 }} />)}</div>
      <div style={{ ...shimmer, height: 340 }} />
      <div style={{ ...shimmer, height: 190 }} />
      <div style={{ textAlign: "center", color: "var(--text-mut)", fontSize: 13, padding: 8 }} className="mono">fetching OHLCV · generating signals · running vectorised P&L…</div>
    </>
  );
}

Object.assign(window, { DashboardPage, BacktestPage, MetricsStrip, Field });
