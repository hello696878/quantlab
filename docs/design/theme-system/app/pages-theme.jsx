/* ============================================================================
   QuantLab — Theme System showcase page
   Demonstrates how ONE accent token re-skins the entire product. Every tile
   reads an accent CSS variable, so the whole board reacts live to the picker.
   Exposed as window.ThemeSystemPage (loaded before pages3.jsx).
   ============================================================================ */
const { useState: useTS } = React;

/* ---- small helpers -------------------------------------------------------- */
function Tile({ label, children, span }) {
  return (
    <div className="glass sheen" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12, gridColumn: span ? `span ${span}` : undefined }}>
      <span className="uplabel">{label}</span>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, flex: 1, justifyContent: "center" }}>{children}</div>
    </div>
  );
}

/* mini two-line chart that reads --accent / --accent-2 */
function MiniChart({ neutral }) {
  const a = neutral ? "var(--text-mut)" : "var(--accent)";
  const a2 = neutral ? "var(--text-faint)" : "var(--accent-2)";
  const s = "M2 40 L16 34 L30 36 L44 24 L58 27 L72 14 L86 18 L98 6";
  const b = "M2 44 L16 41 L30 42 L44 38 L58 39 L72 33 L86 35 L98 30";
  return (
    <svg viewBox="0 0 100 50" width="100%" height="56" preserveAspectRatio="none">
      <path d={b} fill="none" stroke={a2} strokeWidth="1.6" strokeDasharray="3 3" opacity="0.6" />
      <path d={s} fill="none" stroke={a} strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round"
        style={{ filter: neutral ? "none" : "drop-shadow(0 0 4px " + a + ")" }} />
    </svg>
  );
}

/* mini heatmap that follows the accent hue */
function MiniHeat() {
  const h1 = +getComputedStyle(document.documentElement).getPropertyValue("--accent-hue") || 256;
  const h2 = +getComputedStyle(document.documentElement).getPropertyValue("--accent-2-hue") || 205;
  const cells = [0.15, 0.45, 0.9, 0.35, 0.75, 0.55, 0.6, 0.95, 0.25];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 4 }}>
      {cells.map((t, i) => (
        <div key={i} style={{ aspectRatio: "1.6", borderRadius: 5, background: `oklch(${0.27 + t * 0.42} ${0.035 + t * 0.155} ${h2 + (h1 - h2) * t})`,
          border: i === 7 ? "1.5px solid var(--accent-2)" : "1px solid var(--line-faint)" }} />
      ))}
    </div>
  );
}

/* the 'before/after' mini app — accent reaches only the sidebar, or everything */
const NEUTRALIZE = { "--accent": "var(--text-mut)", "--accent-2": "var(--text-faint)", "--accent-rgb": "121,131,154",
  "--accent-soft": "rgba(255,255,255,0.05)", "--accent-softer": "rgba(255,255,255,0.03)", "--accent-line": "var(--line-strong)",
  "--accent-ink": "var(--text-hi)", "--on-accent": "#fff" };

function MiniApp({ reach }) {
  const legacy = reach === "sidebar";
  const contentStyle = legacy ? NEUTRALIZE : {};
  const items = ["Dashboard", "Backtest", "Reports"];
  return (
    <div style={{ display: "flex", borderRadius: 12, overflow: "hidden", border: "1px solid var(--line)", background: "var(--bg-void)", minHeight: 218 }}>
      {/* mini sidebar — keeps real accent in BOTH states */}
      <div style={{ width: 96, padding: 10, borderRight: "1px solid var(--line)", display: "flex", flexDirection: "column", gap: 5, background: "rgba(8,11,20,0.6)" }}>
        <div style={{ width: 20, height: 20, borderRadius: 6, background: "var(--accent-soft)", border: "1px solid var(--accent-line)", marginBottom: 6 }} />
        {items.map((it, i) => (
          <div key={it} className="mono" style={{ fontSize: 9.5, padding: "5px 7px", borderRadius: 6,
            background: i === 0 ? "rgba(var(--accent-rgb),0.12)" : "transparent", color: i === 0 ? "var(--text-hi)" : "var(--text-mut)",
            boxShadow: i === 0 ? "inset 2px 0 0 var(--accent)" : "none" }}>{it}</div>
        ))}
      </div>
      {/* mini content — themed (after) or neutral (before) */}
      <div style={{ flex: 1, padding: 12, display: "flex", flexDirection: "column", gap: 9, ...contentStyle }}>
        <div style={{ display: "flex", gap: 7, alignItems: "center" }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-hi)" }}>Momentum · QQQ</span>
          <span className="badge-accent" style={{ fontSize: 8.5, padding: "2px 6px" }}>Sharpe 1.54</span>
          <button className="btn-primary" style={{ marginLeft: "auto", padding: "5px 11px", fontSize: 10.5 }}>Run</button>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 7 }}>
          <div className="glass" style={{ padding: "7px 9px", borderColor: legacy ? "var(--line)" : "var(--accent-line)", boxShadow: legacy ? "none" : "0 0 18px -8px rgba(var(--accent-rgb),0.6)" }}>
            <div style={{ fontSize: 8, color: "var(--text-mut)", textTransform: "uppercase", letterSpacing: "0.1em" }}>CAGR</div>
            <div className="mono" style={{ fontSize: 15, fontWeight: 700, color: legacy ? "var(--text-hi)" : "var(--accent-ink)" }}>17.6%</div>
          </div>
          <div className="glass" style={{ padding: "7px 9px" }}>
            <div style={{ fontSize: 8, color: "var(--text-mut)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Max DD</div>
            <div className="mono" style={{ fontSize: 15, fontWeight: 700, color: "var(--neg)" }}>-14%</div>
          </div>
        </div>
        <MiniChart neutral={legacy} />
      </div>
    </div>
  );
}

/* ============================================================================
   ThemeSystemPage
   ============================================================================ */
function ThemeSystemPage({ theme, onTheme }) {
  const [reach, setReach] = useTS("all");
  const active = THEMES.find((x) => x.id === theme) || THEMES[0];

  return (
    <div style={{ padding: 28, display: "flex", flexDirection: "column", gap: 18, maxWidth: 1180 }}>
      {/* ---- Theme picker ---- */}
      <Panel title="Accent theme" accent
        right={<span className="mono" style={{ fontSize: 11.5, color: "var(--text-mut)" }}>data-accent="{theme}"</span>}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
          {THEMES.map((th) => {
            const on = th.id === theme;
            return (
              <button key={th.id} onClick={() => onTheme(th.id)} className="glass"
                style={{ padding: 14, textAlign: "left", cursor: "pointer", display: "flex", flexDirection: "column", gap: 10,
                  border: on ? "1px solid " + th.swatch : "1px solid var(--line)",
                  boxShadow: on ? "0 0 24px -8px " + th.swatch : "none" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ width: 28, height: 28, borderRadius: 8, background: th.swatch, boxShadow: "0 0 14px -2px " + th.swatch }} />
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-hi)" }}>{th.label}</div>
                    <div style={{ fontSize: 10.5, color: "var(--text-mut)" }}>{th.note}</div>
                  </div>
                  {on && <span className="mono" style={{ marginLeft: "auto", fontSize: 9.5, color: th.swatch, fontWeight: 700 }}>● LIVE</span>}
                </div>
              </button>
            );
          })}
        </div>
        <p style={{ margin: "14px 0 0", fontSize: 12.5, color: "var(--text-mut)", lineHeight: 1.6, maxWidth: 760 }}>
          One token drives the whole product. Every accent is tuned to the same perceptual lightness and chroma, so switching
          themes restyles the entire terminal without changing its weight or legibility — it always reads as one institutional system.
          Up/down market semantics (<span className="pos">green</span> / <span className="neg">red</span>) stay fixed regardless of accent.
        </p>
      </Panel>

      {/* ---- Before / After ---- */}
      <Panel title="Before · After — accent reach"
        right={
          <div className="tabbar">
            <button className={"tab" + (reach === "sidebar" ? " active" : "")} onClick={() => setReach("sidebar")}>Before</button>
            <button className={"tab" + (reach === "all" ? " active" : "")} onClick={() => setReach("all")}>After</button>
          </div>
        }>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="uplabel">Before</span>
              <span style={{ fontSize: 11.5, color: "var(--text-mut)" }}>accent reaches only the sidebar active state</span>
            </div>
            <MiniApp reach="sidebar" />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="uplabel" style={{ color: "var(--accent-ink)" }}>After</span>
              <span style={{ fontSize: 11.5, color: "var(--text-mut)" }}>buttons · metrics · charts · badges all follow the accent</span>
            </div>
            <MiniApp reach="all" />
          </div>
        </div>
      </Panel>

      {/* ---- Specimen board: every surface the accent touches ---- */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginTop: 2 }}>
        <h3 style={{ margin: 0, fontSize: 15, color: "var(--text-hi)" }}>Surface coverage</h3>
        <span style={{ fontSize: 12.5, color: "var(--text-mut)" }}>every element below reacts live to the <span className="accent-text" style={{ fontWeight: 600 }}>{active.label}</span> accent</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(232px, 1fr))", gap: 12 }}>

        <Tile label="Sidebar active state">
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {["Dashboard", "Backtest"].map((it, i) => (
              <div key={it} className="mono" style={{ fontSize: 12, padding: "8px 10px", borderRadius: 8,
                background: i === 0 ? "rgba(var(--accent-rgb),0.12)" : "transparent", color: i === 0 ? "var(--text-hi)" : "var(--text-mut)",
                boxShadow: i === 0 ? "inset 2px 0 0 var(--accent)" : "none" }}>{it}</div>
            ))}
          </div>
        </Tile>

        <Tile label="Primary · secondary buttons">
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="btn-primary">Run Backtest</button>
            <button className="btn-secondary">Save</button>
          </div>
          <button className="btn-ghost" style={{ alignSelf: "flex-start" }}>Export ↗</button>
        </Tile>

        <Tile label="Input focus ring">
          <input className="field-input" defaultValue="SPY" readOnly style={{ borderColor: "var(--accent)", boxShadow: "0 0 0 3px rgba(var(--accent-rgb),0.22)" }} />
          <span style={{ fontSize: 10.5, color: "var(--text-faint)" }}>focused state</span>
        </Tile>

        <Tile label="Active tabs">
          <div className="tabbar">
            <button className="tab active">Sharpe</button>
            <button className="tab">CAGR</button>
            <button className="tab">Calmar</button>
          </div>
        </Tile>

        <Tile label="Chart primary · secondary line">
          <MiniChart />
          <div style={{ display: "flex", gap: 12, fontSize: 10.5, color: "var(--text-mut)" }}>
            <span style={{ display: "flex", alignItems: "center", gap: 5 }}><span style={{ width: 12, height: 2, background: "var(--accent)" }} />Strategy</span>
            <span style={{ display: "flex", alignItems: "center", gap: 5 }}><span style={{ width: 12, borderTop: "2px dashed var(--accent-2)" }} />Benchmark</span>
          </div>
        </Tile>

        <Tile label="Metric card highlight">
          <div className="glass" style={{ padding: "11px 13px", borderColor: "var(--accent-line)", boxShadow: "0 0 26px -10px rgba(var(--accent-rgb),0.55)" }}>
            <div className="uplabel" style={{ fontSize: 9.5 }}>Blended Sharpe</div>
            <div className="mono" style={{ fontSize: 22, fontWeight: 700, color: "var(--accent-ink)", marginTop: 3 }}>1.51</div>
          </div>
        </Tile>

        <Tile label="Badge colors">
          <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
            <span className="badge-accent">Active</span>
            <Badge tone="pos">+18.4%</Badge>
            <Badge tone="neg">-12.1%</Badge>
            <Badge tone="warn">Overfit</Badge>
          </div>
        </Tile>

        <Tile label="Table selected row">
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11.5 }}>
            <tbody className="mono">
              {[["SMA", "1.18"], ["MOM", "1.54"], ["RSI", "1.07"]].map((r, i) => (
                <tr key={r[0]} className={i === 1 ? "row-selected" : ""}>
                  <td style={{ padding: "7px 8px", color: i === 1 ? "var(--accent-ink)" : "var(--text)" }}>{r[0]}</td>
                  <td style={{ padding: "7px 8px", textAlign: "right", color: "var(--text-hi)" }}>{r[1]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Tile>

        <Tile label="Heatmap accents">
          <MiniHeat />
        </Tile>

        <Tile label="Glow effects">
          <div style={{ display: "flex", gap: 14, alignItems: "center", justifyContent: "center", padding: "6px 0" }}>
            <span style={{ width: 40, height: 40, borderRadius: 999, background: "var(--accent)", boxShadow: "0 0 28px -2px var(--accent), 0 0 60px -10px var(--accent)" }} />
            <button className="btn-primary" style={{ boxShadow: "var(--glow)" }}>Glow</button>
          </div>
        </Tile>

        <Tile label="Report header accent">
          <div className="report-accent-band" />
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-hi)" }}>Q3 Strategy Report</span>
            <span className="badge-accent" style={{ marginLeft: "auto" }}>PDF</span>
          </div>
        </Tile>

        <Tile label="API online indicator">
          <div className="glass" style={{ display: "flex", alignItems: "center", gap: 9, padding: "8px 12px", borderRadius: 999, alignSelf: "flex-start" }}>
            <span className="livedot" /><span className="uplabel" style={{ color: "var(--text)" }}>API</span>
            <span className="mono" style={{ fontSize: 11.5, color: "var(--pos)" }}>200 · 41ms</span>
          </div>
          <span style={{ fontSize: 10.5, color: "var(--text-faint)" }}>status stays green — semantic, not accent</span>
        </Tile>

        <Tile label="Risk / warning cards" span={2}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <AlertCard tone="warn" title="Overfitting risk">Sweep dispersion is high — trust plateaus, not lone peaks.</AlertCard>
            <AlertCard tone="neg" title="OOS collapsed">Out-of-sample Sharpe fell below the benchmark.</AlertCard>
          </div>
        </Tile>

      </div>

      <p style={{ margin: "4px 0 8px", fontSize: 12, color: "var(--text-faint)", lineHeight: 1.6, maxWidth: 760 }}>
        Implementation: each surface reads a single accent variable (<span className="mono">--accent</span>, <span className="mono">--accent-2</span>,
        <span className="mono"> --accent-soft</span>, <span className="mono">--accent-line</span>, or <span className="mono">rgba(var(--accent-rgb), …)</span>).
        Swapping <span className="mono">data-accent</span> on <span className="mono">&lt;html&gt;</span> re-skins all of them at once — see THEME_SYSTEM.md.
      </p>
    </div>
  );
}

window.ThemeSystemPage = ThemeSystemPage;
