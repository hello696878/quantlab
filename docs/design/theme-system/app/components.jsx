/* ============================================================================
   QuantLab — Shared UI components
   Sidebar, TopBar (status), animated MetricCard, StrategySelector,
   ParameterControl, AlertCard, OverfittingPanel, TradeTable, badges.
   Exposed on window for use by pages.jsx.
   ============================================================================ */
const { useState: useStateC, useEffect: useEffectC, useRef: useRefC, useMemo: useMemoC } = React;

/* ---- animated count-up ---------------------------------------------------- */
function useCountUp(target, { dur = 900, decimals = 2 } = {}) {
  // init to target so a hidden/frozen document (no rAF) shows the FINAL value
  const [v, setV] = useStateC(typeof target === "number" ? target : 0);
  const ref = useRefC();
  useEffectC(() => {
    let raf, start;
    const from = ref.current ?? 0;
    function tick(t) {
      if (!start) start = t;
      const p = Math.min(1, (t - start) / dur);
      const e = 1 - Math.pow(1 - p, 3);
      setV(from + (target - from) * e);
      if (p < 1) raf = requestAnimationFrame(tick); else ref.current = target;
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, dur]);
  return v;
}

/* ---- formatters ----------------------------------------------------------- */
const fmt = {
  pct: (x, d = 1) => `${x >= 0 ? "+" : ""}${(x * 100).toFixed(d)}%`,
  pctRaw: (x, d = 1) => `${(x * 100).toFixed(d)}%`,
  num: (x, d = 2) => x.toFixed(d),
  money: (x) => "$" + Math.round(x).toLocaleString("en-US"),
  moneyK: (x) => "$" + (x / 1000).toFixed(1) + "k",
};

/* ---- icons (minimal line glyphs, stroke=currentColor) --------------------- */
const ICONS = {
  dashboard: "M3 13h8V3H3v10Zm10 8h8V3h-8v18ZM3 21h8v-6H3v6Z",
  backtest: "M4 4v16h16M8 16l3-4 3 2 4-6",
  research: "M11 4a7 7 0 1 0 4.95 11.95L20 20M11 4a7 7 0 0 1 7 7",
  compare: "M9 3v18M15 3v18M4 7h5M15 11h5M4 14h5M15 17h5",
  sweep: "M4 4h4v4H4V4Zm6 0h4v4h-4V4Zm6 0h4v4h-4V4ZM4 10h4v4H4v-4Zm6 0h4v4h-4v-4Zm6 0h4v4h-4v-4ZM4 16h4v4H4v-4Zm6 0h4v4h-4v-4Z",
  walkfwd: "M3 17l5-5 4 3 5-7 4 4M3 21h18",
  theme: "M12 3a9 9 0 1 0 0 18c1 0 1.8-.8 1.8-1.8 0-.5-.2-.9-.5-1.2-.3-.3-.4-.7-.4-1 0-.9.8-1.5 1.7-1.5H16A5 5 0 0 0 21 11 9 9 0 0 0 12 3ZM7 13a1.4 1.4 0 1 1 0-2.8A1.4 1.4 0 0 1 7 13Zm3-4a1.4 1.4 0 1 1 0-2.8A1.4 1.4 0 0 1 10 9Zm5 0a1.4 1.4 0 1 1 0-2.8A1.4 1.4 0 0 1 15 9Z",
  tokens: "M12 2 3 7v10l9 5 9-5V7l-9-5Zm0 0v20M3 7l9 5 9-5",
};
function Icon({ name, size = 17 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d={ICONS[name]} /></svg>;
}

/* ---- Logo mark ------------------------------------------------------------ */
function Logo({ size = 30 }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
        <rect x="1" y="1" width="30" height="30" rx="8" fill="rgba(var(--accent-rgb),0.12)" stroke="var(--accent)" strokeOpacity="0.5" />
        <path d="M6 22 L12 13 L17 18 L26 7" stroke="var(--accent)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        <circle cx="26" cy="7" r="2.6" fill="var(--cyan)" />
      </svg>
      <div style={{ lineHeight: 1.05 }}>
        <div style={{ fontWeight: 800, fontSize: 16, letterSpacing: "-0.02em", color: "var(--text-hi)" }}>Quant<span style={{ color: "var(--accent)" }}>Lab</span></div>
        <div className="mono" style={{ fontSize: 9, color: "var(--text-faint)", letterSpacing: "0.14em" }}>RESEARCH TERMINAL</div>
      </div>
    </div>
  );
}

/* ============================================================================
   Sidebar
   ============================================================================ */
const NAV = [
  { id: "dashboard", label: "Dashboard", icon: "dashboard" },
  { id: "backtest", label: "Backtest", icon: "backtest" },
  { id: "research", label: "Research Tools", icon: "research" },
  { id: "compare", label: "Comparison", icon: "compare" },
  { id: "sweep", label: "Parameter Sweep", icon: "sweep" },
  { id: "walkfwd", label: "Walk-Forward", icon: "walkfwd" },
  { id: "theme", label: "Theme System", icon: "theme" },
];
function Sidebar({ active, onNav }) {
  return (
    <aside style={{ width: 224, display: "flex", flexDirection: "column", padding: "20px 14px",
      borderRight: "1px solid var(--line)", background: "rgba(8,11,20,0.55)", backdropFilter: "blur(8px)", position: "fixed", left: 0, top: 0, height: "100vh", zIndex: 30 }}>
      <div style={{ padding: "2px 8px 22px" }}><Logo /></div>
      <nav style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {NAV.map((n) => (
          <button key={n.id} onClick={() => onNav(n.id)} className={"navbtn" + (active === n.id ? " active" : "")}>
            <span className="navicon"><Icon name={n.icon} /></span>
            {n.label}
          </button>
        ))}
      </nav>
      <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 10 }}>
        <button onClick={() => onNav("tokens")} className={"navbtn" + (active === "tokens" ? " active" : "")}
          style={{ border: "1px solid var(--line)" }}>
          <span className="navicon"><Icon name="tokens" /></span> Design Tokens
        </button>
        <div className="glass" style={{ padding: "11px 12px", borderRadius: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 7 }}>
            <span className="livedot" /><span className="uplabel" style={{ color: "var(--text)" }}>Engine online</span>
          </div>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--text-faint)", lineHeight: 1.6 }}>
            FastAPI · v0.4.0<br />yfinance cache · warm
          </div>
        </div>
      </div>
    </aside>
  );
}

/* ============================================================================
   TopBar — context title + ticker chip + clock + API status
   ============================================================================ */
function ApiStatus() {
  const [ping, setPing] = useStateC(38);
  useEffectC(() => { const id = setInterval(() => setPing(28 + Math.round(Math.random() * 26)), 2600); return () => clearInterval(id); }, []);
  return (
    <div className="glass" style={{ display: "flex", alignItems: "center", gap: 9, padding: "6px 12px", borderRadius: 999 }}>
      <span className="livedot" />
      <span className="uplabel" style={{ color: "var(--text)" }}>API</span>
      <span className="mono" style={{ fontSize: 11.5, color: "var(--pos)" }}>200</span>
      <span style={{ width: 1, height: 12, background: "var(--line-strong)" }} />
      <span className="mono" style={{ fontSize: 11.5, color: "var(--text-mut)" }}>{ping}ms</span>
    </div>
  );
}
function Clock() {
  const [t, setT] = useStateC(new Date());
  useEffectC(() => { const id = setInterval(() => setT(new Date()), 1000); return () => clearInterval(id); }, []);
  return <span className="mono" style={{ fontSize: 12, color: "var(--text-mut)" }}>{t.toLocaleTimeString("en-US", { hour12: false })} <span style={{ color: "var(--text-faint)" }}>UTC-5</span></span>;
}

/* ---- Theme catalog (shared by the switcher + Theme System page) ----------- */
const THEMES = [
  { id: "cyan",    label: "Cyan",    swatch: "oklch(0.82 0.13 205)", note: "Default · cool analytics" },
  { id: "blue",    label: "Blue",    swatch: "oklch(0.72 0.16 256)", note: "Classic institutional" },
  { id: "emerald", label: "Emerald", swatch: "oklch(0.80 0.15 162)", note: "Performance / growth" },
  { id: "violet",  label: "Violet",  swatch: "oklch(0.69 0.17 292)", note: "Research / quant lab" },
  { id: "amber",   label: "Amber",   swatch: "oklch(0.82 0.13 78)",  note: "Warm reporting decks" },
  { id: "red",     label: "Risk",    swatch: "oklch(0.64 0.20 22)",  note: "Stress / risk mode" },
];

/* Apply a theme synchronously so any chart that reads CSS vars on its next
   render picks up the new hue immediately (no one-frame lag). */
function applyAccent(id) { document.documentElement.setAttribute("data-accent", id); }

function ThemeSwitcher({ value, onChange, compact }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: compact ? 6 : 8 }}>
      {!compact && <span className="uplabel" style={{ marginRight: 2 }}>Theme</span>}
      <div style={{ display: "flex", gap: 6 }}>
        {THEMES.map((th) => (
          <button key={th.id} className="swatch" data-on={value === th.id} title={th.label}
            onClick={() => { applyAccent(th.id); onChange(th.id); }}
            style={{ background: th.swatch, color: th.swatch }} aria-label={th.label} />
        ))}
      </div>
    </div>
  );
}

function TopBar({ title, subtitle, right, theme, onTheme }) {
  return (
    <header style={{ display: "flex", alignItems: "center", gap: 16, padding: "16px 28px", borderBottom: "1px solid var(--line)",
      position: "sticky", top: 0, zIndex: 20, background: "rgba(8,11,20,0.72)", backdropFilter: "blur(12px)" }}>
      <div style={{ minWidth: 0 }}>
        <h1 style={{ margin: 0, fontSize: 19, fontWeight: 700, color: "var(--text-hi)", letterSpacing: "-0.01em" }}>{title}</h1>
        {subtitle && <p style={{ margin: "2px 0 0", fontSize: 12.5, color: "var(--text-mut)" }}>{subtitle}</p>}
      </div>
      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
        {right}
        {onTheme && <ThemeSwitcher value={theme} onChange={onTheme} compact />}
        <span style={{ width: 1, height: 20, background: "var(--line-strong)" }} />
        <Clock />
        <ApiStatus />
      </div>
    </header>
  );
}

/* ============================================================================
   MetricCard — animated value, optional delta + sparkline
   ============================================================================ */
function MetricCard({ label, value, format = "num", decimals = 2, delta, deltaTone, spark, sparkColor, accent, sub, delay = 0 }) {
  const animated = useCountUp(typeof value === "number" ? value : 0, { dur: 1000 + delay });
  let display;
  if (typeof value !== "number") display = value;
  else if (format === "pct") display = fmt.pct(animated, decimals);
  else if (format === "pctRaw") display = fmt.pctRaw(animated, decimals);
  else if (format === "money") display = fmt.money(animated);
  else if (format === "moneyK") display = fmt.moneyK(animated);
  else display = animated.toFixed(decimals);

  const tone = deltaTone === "pos" ? "var(--pos)" : deltaTone === "neg" ? "var(--neg)" : deltaTone === "warn" ? "var(--warn)" : "var(--text-mut)";
  return (
    <div className="glass sheen rise" style={{ padding: "16px 17px", display: "flex", flexDirection: "column", gap: 9, minHeight: 104,
      borderColor: accent ? "color-mix(in oklch, var(--accent) 32%, var(--line))" : undefined,
      boxShadow: accent ? "var(--glow-soft)" : undefined, animationDelay: delay + "ms" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
        <span className="uplabel" style={{ flex: 1, minWidth: 0 }}>{label}</span>
        {delta != null && (
          <span className="mono" style={{ fontSize: 11.5, color: tone, fontWeight: 600, whiteSpace: "nowrap", flexShrink: 0,
            background: deltaTone === "pos" ? "var(--pos-soft)" : deltaTone === "neg" ? "var(--neg-soft)" : "var(--glass)",
            padding: "2px 7px", borderRadius: 999 }}>{delta}</span>
        )}
      </div>
      <div className="mono" style={{ fontSize: "clamp(21px, 2vw, 26px)", fontWeight: 700, color: accent ? "var(--accent)" : "var(--text-hi)", letterSpacing: "-0.02em", lineHeight: 1, whiteSpace: "nowrap" }}>{display}</div>
      {spark ? <Sparkline values={spark} width={150} height={28} color={sparkColor} /> : sub ? <span style={{ fontSize: 11.5, color: "var(--text-faint)" }}>{sub}</span> : null}
    </div>
  );
}

/* ---- Badge / Chip --------------------------------------------------------- */
function Badge({ children, tone = "mut", solid = false }) {
  const map = { pos: "var(--pos)", neg: "var(--neg)", warn: "var(--warn)", accent: "var(--accent)", cyan: "var(--cyan)", mut: "var(--text-mut)" };
  const col = map[tone] || map.mut;
  return (
    <span className="mono" style={{ fontSize: 10.5, fontWeight: 600, letterSpacing: "0.04em", padding: "3px 8px", borderRadius: 999,
      color: solid ? "#06080f" : col, background: solid ? col : `color-mix(in oklch, ${col} 15%, transparent)`,
      border: solid ? "none" : `1px solid color-mix(in oklch, ${col} 35%, transparent)`, textTransform: "uppercase", whiteSpace: "nowrap" }}>{children}</span>
  );
}

/* ============================================================================
   StrategySelector — dropdown of the 6 strategies
   ============================================================================ */
function StrategySelector({ value, onChange, options }) {
  const [open, setOpen] = useStateC(false);
  const ref = useRefC();
  useEffectC(() => { function h(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); } document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h); }, []);
  const sel = options.find((o) => o.id === value);
  return (
    <div ref={ref} style={{ position: "relative", minWidth: 230 }}>
      <button onClick={() => setOpen((o) => !o)} className="glass"
        style={{ width: "100%", display: "flex", alignItems: "center", gap: 11, padding: "10px 13px", borderRadius: 12, cursor: "pointer", color: "var(--text-hi)" }}>
        <span style={{ width: 28, height: 28, borderRadius: 8, background: "rgba(var(--accent-rgb),0.14)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 700 }}>{sel.short}</span>
        <div style={{ textAlign: "left", flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13.5, fontWeight: 600 }}>{sel.name}</div>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--text-mut)" }}>{sel.ticker} · {sel.params}</div>
        </div>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-mut)" strokeWidth="2" style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .2s" }}><path d="M6 9l6 6 6-6" /></svg>
      </button>
      {open && (
        <div className="glass" style={{ position: "absolute", top: "calc(100% + 6px)", left: 0, right: 0, zIndex: 40, padding: 6, borderRadius: 12, boxShadow: "var(--sh-lg)", maxHeight: 340, overflowY: "auto" }}>
          {options.map((o) => (
            <button key={o.id} onClick={() => { onChange(o.id); setOpen(false); }}
              style={{ width: "100%", display: "flex", alignItems: "center", gap: 10, padding: "9px 10px", borderRadius: 9, border: "none", cursor: "pointer",
                background: o.id === value ? "rgba(var(--accent-rgb),0.12)" : "transparent", color: "var(--text)", textAlign: "left" }}
              onMouseEnter={(e) => { if (o.id !== value) e.currentTarget.style.background = "var(--glass)"; }}
              onMouseLeave={(e) => { if (o.id !== value) e.currentTarget.style.background = "transparent"; }}>
              <span style={{ width: 26, height: 26, borderRadius: 7, background: "var(--glass-strong)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-mono)", fontSize: 9.5, fontWeight: 700 }}>{o.short}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-hi)" }}>{o.name}</div>
                <div style={{ fontSize: 11, color: "var(--text-mut)" }}>{o.desc}</div>
              </div>
              <span className="mono" style={{ fontSize: 10.5, color: "var(--text-faint)" }}>{o.ticker}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ============================================================================
   ParameterControl — labeled slider with mono value + stepper
   ============================================================================ */
function ParamSlider({ label, value, min, max, step = 1, unit = "", onChange }) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 12.5, color: "var(--text-mut)" }}>{label}</span>
        <span className="mono" style={{ fontSize: 13, color: "var(--text-hi)", fontWeight: 600 }}>{value}{unit}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(parseFloat(e.target.value))}
        style={{ width: "100%", height: 4, borderRadius: 999, appearance: "none", cursor: "pointer", outline: "none",
          background: `linear-gradient(90deg, var(--accent) ${pct}%, var(--glass-strong) ${pct}%)` }} />
    </div>
  );
}

/* ============================================================================
   AlertCard — warning / overfitting / info
   ============================================================================ */
function AlertCard({ tone = "warn", title, children, icon }) {
  const col = tone === "neg" ? "var(--neg)" : tone === "warn" ? "var(--warn)" : tone === "pos" ? "var(--pos)" : "var(--accent)";
  const soft = tone === "neg" ? "var(--neg-soft)" : tone === "warn" ? "var(--warn-soft)" : tone === "pos" ? "var(--pos-soft)" : "rgba(var(--accent-rgb),0.12)";
  return (
    <div className="rise" style={{ display: "flex", gap: 13, padding: "14px 16px", borderRadius: 14, background: soft, border: `1px solid color-mix(in oklch, ${col} 35%, transparent)` }}>
      <div style={{ flexShrink: 0, width: 30, height: 30, borderRadius: 9, background: `color-mix(in oklch, ${col} 22%, transparent)`, color: col, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          {icon === "shield" ? <path d="M12 2 4 5v6c0 5 3.5 8 8 11 4.5-3 8-6 8-11V5l-8-3Z" /> : <><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.6 2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.6a2 2 0 0 0-3.4 0Z" /></>}
        </svg>
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13.5, fontWeight: 700, color: col, marginBottom: 3 }}>{title}</div>
        <div style={{ fontSize: 12.5, color: "var(--text)", lineHeight: 1.55 }}>{children}</div>
      </div>
    </div>
  );
}

/* ============================================================================
   TradeTable
   ============================================================================ */
function TradeTable({ trades, limit = 9 }) {
  const [showAll, setShowAll] = useStateC(false);
  const rows = showAll ? trades : trades.slice(0, limit);
  return (
    <div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
          <thead>
            <tr style={{ textAlign: "left" }}>
              {["Date", "Action", "Price", "Shares", "Cost"].map((h, i) => (
                <th key={h} className="uplabel" style={{ padding: "0 0 10px", textAlign: i > 1 ? "right" : "left", fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="mono">
            {rows.map((t, i) => (
              <tr key={i} style={{ borderTop: "1px solid var(--line-faint)" }}>
                <td style={{ padding: "9px 0", color: "var(--text-mut)" }}>{t.date}</td>
                <td style={{ padding: "9px 0" }}><Badge tone={t.action === "BUY" || t.action === "LONG SPREAD" ? "pos" : t.action === "EXIT" ? "mut" : "neg"}>{t.action}</Badge></td>
                <td style={{ padding: "9px 0", textAlign: "right", color: "var(--text-hi)" }}>${t.price.toFixed(2)}</td>
                <td style={{ padding: "9px 0", textAlign: "right", color: "var(--text)" }}>{t.shares}</td>
                <td style={{ padding: "9px 0", textAlign: "right", color: "var(--text-mut)" }}>${t.cost.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {trades.length > limit && (
        <button onClick={() => setShowAll((s) => !s)} style={{ marginTop: 12, width: "100%", padding: "8px", borderRadius: 9, border: "1px solid var(--line)", background: "var(--glass)", color: "var(--text-mut)", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
          {showAll ? "Show less" : `Show all ${trades.length} trade events`}
        </button>
      )}
    </div>
  );
}

/* ---- Panel / Section header ----------------------------------------------- */
function Panel({ title, right, children, style, pad = 18, accent }) {
  return (
    <section className="glass sheen" style={{ padding: pad, boxShadow: accent ? "var(--glow-soft)" : undefined, ...style }}>
      {(title || right) && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          {title && <h3 className="uplabel" style={{ margin: 0, fontSize: 11.5, color: "var(--text)" }}>{title}</h3>}
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

/* ---- Run button with loading state ---------------------------------------- */
function RunButton({ loading, onClick, children = "Run Backtest" }) {
  return (
    <button onClick={onClick} disabled={loading}
      style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 9, padding: "11px 20px", borderRadius: 11, border: "none", cursor: loading ? "default" : "pointer",
        background: "linear-gradient(135deg, var(--accent), color-mix(in oklch, var(--accent) 70%, var(--cyan)))", color: "#04060d", fontWeight: 700, fontSize: 13.5,
        boxShadow: "var(--glow)", opacity: loading ? 0.7 : 1, transition: "transform .12s var(--ease), opacity .2s" }}
      onMouseDown={(e) => (e.currentTarget.style.transform = "scale(0.97)")}
      onMouseUp={(e) => (e.currentTarget.style.transform = "scale(1)")}
      onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}>
      {loading ? <><svg width="15" height="15" viewBox="0 0 24 24" fill="none" style={{ animation: "spin 0.8s linear infinite" }}><circle cx="12" cy="12" r="9" stroke="rgba(0,0,0,0.25)" strokeWidth="3" /><path d="M21 12a9 9 0 0 0-9-9" stroke="#04060d" strokeWidth="3" strokeLinecap="round" /></svg> Running…</>
        : <><svg width="14" height="14" viewBox="0 0 24 24" fill="#04060d"><path d="M7 5v14l11-7z" /></svg>{children}</>}
    </button>
  );
}

Object.assign(window, { useCountUp, fmt, Icon, Logo, Sidebar, NAV, TopBar, ApiStatus, MetricCard, Badge, StrategySelector, ParamSlider, AlertCard, TradeTable, Panel, RunButton, THEMES, ThemeSwitcher, applyAccent });
