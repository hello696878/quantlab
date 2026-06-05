/* ============================================================================
   QuantLab — Pages part 3: Design Tokens reference + App router
   ============================================================================ */
const { useState: useS3, useEffect: useE3 } = React;

/* ---- Tweak defaults ------------------------------------------------------- */
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "cyan",
  "glow": "med",
  "cardstyle": "glass",
  "grid": true
}/*EDITMODE-END*/;

/* ============================================================================
   DESIGN TOKENS  — the system, documented in-app (great for screenshots)
   ============================================================================ */
function TokensPage() {
  const colors = [
    { name: "--bg-base", val: "#080b14", note: "App background" },
    { name: "--bg-panel", val: "#0c1120", note: "Solid panels" },
    { name: "--bg-elev", val: "#11182b", note: "Raised elements" },
    { name: "--accent", val: "oklch(.72 .16 256)", note: "Primary · electric blue" },
    { name: "--cyan", val: "oklch(.82 .13 205)", note: "Secondary accent" },
    { name: "--emerald / --pos", val: "oklch(.80 .15 162)", note: "Gains" },
    { name: "--neg", val: "oklch(.68 .19 18)", note: "Losses" },
    { name: "--warn", val: "oklch(.82 .14 80)", note: "Warnings" },
  ];
  const text = [["--text-hi", "Primary text"], ["--text", "Body text"], ["--text-mut", "Muted / labels"], ["--text-faint", "Faint / disabled"]];
  const type = [
    { t: "Display 3xl", px: 42, w: 700, f: "ui", s: "Manrope · headlines" },
    { t: "Title xl", px: 24, w: 700, f: "ui", s: "Manrope · section titles" },
    { t: "Body base", px: 14.5, w: 500, f: "ui", s: "Manrope · UI text" },
    { t: "Metric value", px: 26, w: 700, f: "mono", s: "JetBrains Mono · figures" },
    { t: "Data / mono", px: 13, w: 500, f: "mono", s: "JetBrains Mono · tables, tickers" },
    { t: "Uplabel", px: 10.5, w: 600, f: "ui", s: "uppercase · tracked labels", up: true },
  ];
  const spacing = [4, 8, 12, 16, 24, 32, 48, 64];
  const radii = [["--r-xs", 6], ["--r-sm", 9], ["--r-md", 13], ["--r-lg", 18], ["--r-xl", 24]];
  const shadows = [["--sh-sm", "var(--sh-sm)"], ["--sh-md", "var(--sh-md)"], ["--sh-lg", "var(--sh-lg)"], ["--glow", "var(--glow)"]];

  return (
    <div style={{ padding: 28, display: "flex", flexDirection: "column", gap: 18, maxWidth: 1100 }}>
      <Panel title="Color · surfaces & accents">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
          {colors.map((c) => (
            <div key={c.name} className="glass" style={{ borderRadius: 12, overflow: "hidden" }}>
              <div style={{ height: 56, background: c.val.startsWith("#") ? c.val : `var(${c.name.split(" ")[0]})` }} />
              <div style={{ padding: "9px 11px" }}>
                <div className="mono" style={{ fontSize: 11, color: "var(--text-hi)" }}>{c.name}</div>
                <div className="mono" style={{ fontSize: 10, color: "var(--text-faint)", marginTop: 2 }}>{c.val}</div>
                <div style={{ fontSize: 11, color: "var(--text-mut)", marginTop: 4 }}>{c.note}</div>
              </div>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 18, marginTop: 16, flexWrap: "wrap" }}>
          {text.map(([v, n]) => (
            <div key={v} style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <span style={{ width: 22, height: 22, borderRadius: 6, background: `var(${v})`, border: "1px solid var(--line)" }} />
              <div><div className="mono" style={{ fontSize: 11, color: "var(--text-hi)" }}>{v}</div><div style={{ fontSize: 10.5, color: "var(--text-mut)" }}>{n}</div></div>
            </div>
          ))}
        </div>
      </Panel>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 14 }}>
        <Panel title="Typography">
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {type.map((r) => (
              <div key={r.t} style={{ display: "flex", alignItems: "baseline", gap: 16, borderBottom: "1px solid var(--line-faint)", paddingBottom: 12 }}>
                <span style={{ fontFamily: r.f === "mono" ? "var(--font-mono)" : "var(--font-ui)", fontSize: Math.min(r.px, 30), fontWeight: r.w, color: "var(--text-hi)", textTransform: r.up ? "uppercase" : "none", letterSpacing: r.up ? "0.13em" : "-0.01em", flex: 1 }}>{r.t}</span>
                <span className="mono" style={{ fontSize: 11, color: "var(--text-faint)", whiteSpace: "nowrap" }}>{r.px}px · {r.w}</span>
              </div>
            ))}
            <div style={{ fontSize: 11.5, color: "var(--text-mut)" }}>{type.map((r) => r.s).filter((v, i, a) => a.indexOf(v) === i).slice(0, 2).join(" · ")}</div>
          </div>
        </Panel>
        <Panel title="Spacing · 4px base">
          <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
            {spacing.map((s) => (
              <div key={s} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span className="mono" style={{ fontSize: 11, color: "var(--text-mut)", width: 34 }}>{s}px</span>
                <span style={{ height: 12, width: s, background: "var(--accent)", borderRadius: 3, opacity: 0.7 }} />
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <Panel title="Border radius">
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
            {radii.map(([n, v]) => (
              <div key={n} style={{ textAlign: "center" }}>
                <div style={{ width: 64, height: 52, background: "var(--glass-strong)", border: "1px solid var(--line-strong)", borderRadius: v }} />
                <div className="mono" style={{ fontSize: 10.5, color: "var(--text-mut)", marginTop: 6 }}>{v}px</div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Elevation & glow">
          <div style={{ display: "flex", gap: 18, flexWrap: "wrap", padding: "6px 0" }}>
            {shadows.map(([n, v]) => (
              <div key={n} style={{ textAlign: "center" }}>
                <div style={{ width: 64, height: 52, background: "var(--bg-elev)", borderRadius: 12, boxShadow: v, border: "1px solid var(--line)" }} />
                <div className="mono" style={{ fontSize: 10, color: "var(--text-mut)", marginTop: 8 }}>{n}</div>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel title="Components">
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <Badge tone="pos">+18.4%</Badge><Badge tone="neg">-12.1%</Badge><Badge tone="warn">overfit</Badge>
          <Badge tone="accent">SMA</Badge><Badge tone="cyan" solid>best</Badge>
          <RunButton loading={false} onClick={() => {}} children="Run Backtest" />
          <span className="glass" style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 12px", borderRadius: 999 }}><span className="livedot" /><span className="uplabel" style={{ color: "var(--text)" }}>live</span></span>
        </div>
      </Panel>
    </div>
  );
}

/* ============================================================================
   APP ROUTER + SHELL
   ============================================================================ */
const PAGE_META = {
  dashboard: { title: "Dashboard", sub: "Portfolio overview across all active strategies" },
  backtest: { title: "Backtest Workspace", sub: "Configure, run, and inspect a single strategy" },
  research: { title: "Research Tools", sub: "Out-of-sample validation & robustness analysis" },
  compare: { title: "Strategy Comparison", sub: "Rank strategies side-by-side on one asset" },
  sweep: { title: "Parameter Sweep", sub: "Scan the parameter grid for robust regions" },
  walkfwd: { title: "Walk-Forward Optimization", sub: "Rolling re-optimization with stitched OOS equity" },
  theme: { title: "Theme System", sub: "One accent token — applied across the entire product" },
  tokens: { title: "Design Tokens", sub: "The visual system behind QuantLab Terminal" },
};

function App() {
  const [page, setPage] = useS3(() => location.hash.replace("#", "") || "dashboard");
  const [arg, setArg] = useS3(null);
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  // drive the data-* attributes that tokens.css reads
  useE3(() => {
    const r = document.documentElement;
    r.setAttribute("data-accent", t.accent);
    r.setAttribute("data-glow", t.glow);
    r.setAttribute("data-cardstyle", t.cardstyle);
    r.style.setProperty("--grid-display", t.grid ? "block" : "none");
  }, [t.accent, t.glow, t.cardstyle, t.grid]);

  useE3(() => {
    window.__qlnav = (p, a) => { setPage(p); setArg(a || null); location.hash = p; window.scrollTo({ top: 0 }); };
    return () => { delete window.__qlnav; };
  }, []);

  const meta = PAGE_META[page] || PAGE_META.dashboard;
  const setTheme = (a) => { applyAccent(a); setTweak("accent", a); };
  let body;
  if (page === "dashboard") body = <DashboardPage />;
  else if (page === "backtest") body = <BacktestPage key={arg || "default"} initialStrategy={arg} />;
  else if (page === "research") body = <ResearchPage />;
  else if (page === "compare") body = <ComparePage />;
  else if (page === "sweep") body = <SweepPage />;
  else if (page === "walkfwd") body = <WalkForwardPage />;
  else if (page === "theme") body = <ThemeSystemPage theme={t.accent} onTheme={setTheme} />;
  else if (page === "tokens") body = <TokensPage />;
  else body = <DashboardPage />;

  return (
    <div style={{ minHeight: "100vh" }}>
      <Sidebar active={page} onNav={(p) => window.__qlnav(p)} />
      <div id="scroll-main" style={{ marginLeft: 224, minWidth: 0, minHeight: "100vh" }}>
        <TopBar title={meta.title} subtitle={meta.sub} theme={t.accent} onTheme={setTheme} />
        <main key={page + ":" + t.accent} className="rise">{body}</main>
      </div>
      <TweaksPanel title="Tweaks">
        <TweakSection label="Accent theme" />
        <TweakRadio label="Primary" value={t.accent} options={["cyan", "blue", "emerald"]} onChange={setTheme} />
        <TweakRadio label="More" value={t.accent} options={["violet", "amber", "red"]} onChange={setTheme} />
        <TweakSection label="Surface & depth" />
        <TweakRadio label="Glow" value={t.glow} options={["low", "med", "high"]} onChange={(v) => setTweak("glow", v)} />
        <TweakRadio label="Cards" value={t.cardstyle} options={["glass", "solid", "outline"]} onChange={(v) => setTweak("cardstyle", v)} />
        <TweakToggle label="Grid background" value={t.grid} onChange={(v) => setTweak("grid", v)} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
