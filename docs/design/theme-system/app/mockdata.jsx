/* ============================================================================
   QuantLab — Mock data engine
   Deterministic (seeded) generators that mirror the real backend response
   shapes from backend/app/schemas.py (PerformanceMetrics, EquityPoint,
   SmaSweepRow, walk-forward windows, strategy comparison, trades).
   Nothing here hits a network. Exposed on window.QL.
   ============================================================================ */
(function () {
  // ---- Seeded PRNG (mulberry32) so charts are stable across reloads -------
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  // gaussian
  function gauss(r) { return Math.sqrt(-2 * Math.log(r() + 1e-12)) * Math.cos(2 * Math.PI * r()); }

  const DAY = 86400000;
  function dateStr(t) { return new Date(t).toISOString().slice(0, 10); }

  // ---- Generate a daily-ish equity curve via GBM with regime + a drawdown -
  // Returns { points:[{date,strategy,benchmark}], dailyRet:[], benchRet:[] }
  // Weekly bars: 480 bars × 7d ≈ 9.2y span, so periods/year ≈ 52 (matches YEARS).
  function genCurve({ seed, n = 480, startDate = "2015-01-01", drift = 0.0035, vol = 0.020,
                      benchDrift = 0.0024, benchVol = 0.021, initial = 100000, crashes = [] }) {
    const r = rng(seed);
    let t0 = Date.parse(startDate);
    let eq = initial, bm = initial;
    const points = [], dailyRet = [], benchRet = [];
    for (let i = 0; i < n; i++) {
      // strategy return: drift + vol shock, with optional engineered drawdowns.
      // A crash is a DESCENT into a trough at c.at over c.width bars (negative
      // drag + mild vol bump); normal drift then recovers the curve. This makes
      // realistic peak-to-trough drawdowns without permanently sinking returns.
      let dr = drift, regime = 1;
      crashes.forEach((c) => {
        if (i <= c.at && i > c.at - c.width) {
          const tri = 1 - (c.at - i) / c.width;
          regime += 0.5 * tri; dr -= c.depth * tri;
        }
      });
      const sret = dr + vol * gauss(r) * regime;
      const bret = benchDrift + benchVol * gauss(r) * (1 + (regime - 1) * 0.8);
      eq *= 1 + sret; bm *= 1 + bret;
      dailyRet.push(sret); benchRet.push(bret);
      points.push({ date: dateStr(t0 + i * DAY * 7), strategy: +eq.toFixed(2), benchmark: +bm.toFixed(2) });
    }
    return { points, dailyRet, benchRet, initial };
  }

  // ---- Derive PerformanceMetrics from a return series (internally consistent)
  function metricsFrom(rets, equity, years) {
    const n = rets.length;
    const mean = rets.reduce((a, b) => a + b, 0) / n;
    const sd = Math.sqrt(rets.reduce((a, b) => a + (b - mean) ** 2, 0) / n);
    const down = rets.filter((x) => x < 0);
    const dsd = Math.sqrt((down.reduce((a, b) => a + b * b, 0) / n) || 1e-9);
    const periodsPerYear = n / years;
    const total = equity[equity.length - 1] / equity[0] - 1;
    const cagr = Math.pow(1 + total, 1 / years) - 1;
    // max drawdown
    let peak = -Infinity, mdd = 0;
    for (const v of equity) { peak = Math.max(peak, v); mdd = Math.min(mdd, v / peak - 1); }
    const vola = sd * Math.sqrt(periodsPerYear);
    const sharpe = (mean / (sd || 1e-9)) * Math.sqrt(periodsPerYear);
    const sortino = (mean / (dsd || 1e-9)) * Math.sqrt(periodsPerYear);
    const calmar = cagr / (Math.abs(mdd) || 1e-9);
    const win = rets.filter((x) => x > 0).length / n;
    return {
      total_return: total, cagr, sharpe_ratio: sharpe, sortino_ratio: sortino,
      max_drawdown: mdd, volatility: vola, calmar_ratio: calmar, win_rate: win, num_days: n,
    };
  }

  // ---- Calibrate a raw return series to hit a target (CAGR, Sharpe) -------
  // Preserves the SHAPE (wiggle + engineered drawdowns) but shifts/scales so
  // realized annualized stats land on target. periodsPerYear ≈ 52 (weekly).
  function calibrate(rets, { cagr, sharpe }, ppy = 52) {
    const n = rets.length;
    const meanRaw = rets.reduce((a, b) => a + b, 0) / n;
    const sdRaw = Math.sqrt(rets.reduce((a, b) => a + (b - meanRaw) ** 2, 0) / n) || 1e-9;
    const desiredSd = Math.log(1 + cagr) / (Math.sqrt(ppy) * sharpe);
    const desiredMean = Math.log(1 + cagr) / ppy + 0.5 * desiredSd * desiredSd;
    const k = desiredSd / sdRaw;
    return rets.map((x) => desiredMean + (x - meanRaw) * k);
  }
  function equityFrom(rets, initial = 100000, startDate = "2015-01-01") {
    let eq = initial, t0 = Date.parse(startDate);
    return rets.map((r, i) => { eq *= 1 + r; return { date: dateStr(t0 + i * DAY * 7), strategy: +eq.toFixed(2) }; });
  }

  // ---- Equity → drawdown series ------------------------------------------
  function drawdownSeries(points, key = "strategy") {
    let peak = -Infinity;
    return points.map((p) => { peak = Math.max(peak, p[key]); return { date: p.date, dd: p[key] / peak - 1 }; });
  }

  // ---- Trades ------------------------------------------------------------
  function genTrades(seed, points, count = 42) {
    const r = rng(seed);
    const out = [];
    let holding = false;
    for (let k = 0; k < count; k++) {
      const idx = Math.floor((k / count) * (points.length - 2)) + 1;
      const p = points[idx];
      holding = !holding;
      const price = 180 + gauss(r) * 30 + idx * 0.18;
      const shares = Math.round(120 + r() * 380);
      out.push({
        date: p.date,
        action: holding ? "BUY" : "SELL",
        price: +Math.max(40, price).toFixed(2),
        shares,
        cost: +(shares * Math.max(40, price) * (0.001)).toFixed(2),
      });
    }
    return out.reverse();
  }

  // ========================================================================
  //  STRATEGY CATALOG  (mirrors strategies.py)
  // ========================================================================
  const STRATEGIES = [
    { id: "sma_crossover",       name: "SMA Crossover",        short: "SMA",  ticker: "SPY",  seed: 101,
      params: "50 / 200", desc: "Trend-following dual moving-average crossover.", drift: 0.00262, vol: 0.0136,
      crashes: [{ at: 150, depth: 0.0090, width: 30 }, { at: 360, depth: 0.0075, width: 26 }], target: { cagr: 0.118, sharpe: 1.18 } },
    { id: "momentum",            name: "Time-Series Momentum", short: "MOM",  ticker: "QQQ",  seed: 209,
      params: "126d · 0.0", desc: "Long when trailing 6-month return is positive.", drift: 0.00352, vol: 0.0148,
      crashes: [{ at: 300, depth: 0.0115, width: 30 }], target: { cagr: 0.176, sharpe: 1.54 } },
    { id: "rsi_mean_reversion",  name: "RSI Mean Reversion",   short: "RSI",  ticker: "AAPL", seed: 305,
      params: "14 · 30→50", desc: "Buy oversold dips, exit on RSI recovery.", drift: 0.00196, vol: 0.0114,
      crashes: [{ at: 210, depth: 0.0070, width: 26 }], target: { cagr: 0.092, sharpe: 1.07 } },
    { id: "bollinger_band",      name: "Bollinger Reversion",  short: "BB",   ticker: "MSFT", seed: 404,
      params: "20 · 2σ", desc: "Mean-revert from the lower band to the mean.", drift: 0.00224, vol: 0.0107,
      crashes: [{ at: 260, depth: 0.0058, width: 22 }], target: { cagr: 0.108, sharpe: 1.36 } },
    { id: "volatility_breakout", name: "Volatility Breakout",  short: "VOL",  ticker: "NVDA", seed: 511,
      params: "20 · 1.0×", desc: "Enter on range breakouts above prior high.", drift: 0.00402, vol: 0.0211,
      crashes: [{ at: 180, depth: 0.0150, width: 28 }, { at: 380, depth: 0.0130, width: 24 }], target: { cagr: 0.205, sharpe: 1.24 } },
    { id: "pairs",               name: "Pairs (KO / PEP)",     short: "PAIR", ticker: "KO·PEP", seed: 606,
      params: "z 2.0 / 0.5", desc: "Dollar-neutral stat-arb on the spread.", drift: 0.00150, vol: 0.0063,
      crashes: [{ at: 240, depth: 0.0034, width: 18 }], target: { cagr: 0.073, sharpe: 1.61 } },
  ];

  // Build a full backtest result for each strategy
  const YEARS = 9.2; // 2015 → 2024 (480 weekly bars)
  function buildStrategy(s) {
    const c = genCurve({ seed: s.seed, drift: s.drift, vol: s.vol, crashes: s.crashes });
    // calibrate strategy returns to the target (CAGR, Sharpe); benchmark to SPY-like
    const sRet = s.target ? calibrate(c.dailyRet, s.target) : c.dailyRet;
    const bRet = calibrate(c.benchRet, { cagr: 0.094, sharpe: 0.66 });
    const sEq = equityFrom(sRet);
    const bEq = equityFrom(bRet);
    const points = sEq.map((p, i) => ({ date: p.date, strategy: p.strategy, benchmark: bEq[i].strategy }));
    const m = metricsFrom(sRet, points.map((p) => p.strategy), YEARS);
    const bm = metricsFrom(bRet, points.map((p) => p.benchmark), YEARS);
    return {
      ...s,
      equity_curve: points,
      drawdown: drawdownSeries(points),
      strategy_metrics: m,
      benchmark_metrics: bm,
      trades: genTrades(s.seed + 7, points, s.id === "sma_crossover" ? 38 : 30),
      num_trades: s.id === "sma_crossover" ? 38 : 30,
      spark: points.filter((_, i) => i % 12 === 0).map((p) => p.strategy),
    };
  }

  const BUILT = {};
  STRATEGIES.forEach((s) => (BUILT[s.id] = buildStrategy(s)));

  // ========================================================================
  //  PARAMETER SWEEP  (SmaSweepRow[])  — smooth surface with a robust plateau
  // ========================================================================
  const FAST = [10, 20, 30, 40, 50, 60];
  const SLOW = [60, 90, 120, 150, 180, 210, 240];
  function buildSweep() {
    const r = rng(909);
    const rows = [];
    // sharpe surface: peak near fast~30, ratio slow/fast ~ 4; noise = overfit spikes
    FAST.forEach((f) => {
      SLOW.forEach((sl) => {
        if (f >= sl) return;
        const ratio = sl / f;
        const surf = 1.35 * Math.exp(-((f - 30) ** 2) / 900) * Math.exp(-((ratio - 4.2) ** 2) / 14);
        const noise = (gauss(r)) * 0.10;
        const sharpe = Math.max(-0.4, surf + 0.45 + noise);
        const cagr = 0.04 + sharpe * 0.06 + gauss(r) * 0.01;
        const mdd = -(0.12 + (1.4 - sharpe) * 0.10 + Math.abs(gauss(r)) * 0.03);
        rows.push({
          fast_window: f, slow_window: sl,
          sharpe_ratio: +sharpe.toFixed(2),
          cagr: +cagr.toFixed(4),
          total_return: +(Math.pow(1 + cagr, YEARS) - 1).toFixed(4),
          sortino_ratio: +(sharpe * 1.35).toFixed(2),
          calmar_ratio: +(cagr / Math.abs(mdd)).toFixed(2),
          max_drawdown: +mdd.toFixed(4),
          volatility: +(0.14 + Math.abs(gauss(r)) * 0.02).toFixed(4),
          num_trades: Math.round(20 + ratio * 4 + r() * 10),
        });
      });
    });
    return rows;
  }
  const SWEEP = buildSweep();
  const SWEEP_BEST = SWEEP.reduce((a, b) => (b.sharpe_ratio > a.sharpe_ratio ? b : a), SWEEP[0]);

  // ========================================================================
  //  TRAIN / TEST  (SmaTrainTestResponse-ish)
  // ========================================================================
  const TRAINTEST = {
    ticker: "SPY", start_date: "2015-01-01", split_date: "2021-01-01", end_date: "2023-12-31",
    selection_metric: "sharpe_ratio",
    in_sample_days: 1510, out_of_sample_days: 754,
    best_fast_window: 30, best_slow_window: 130,
    in_sample_metrics: { sharpe_ratio: 1.42, cagr: 0.171, calmar_ratio: 1.18, max_drawdown: -0.145, total_return: 1.62, sortino_ratio: 1.95, volatility: 0.142, win_rate: 0.566, num_days: 1510 },
    out_of_sample_metrics: { sharpe_ratio: 0.61, cagr: 0.068, calmar_ratio: 0.41, max_drawdown: -0.166, total_return: 0.141, sortino_ratio: 0.82, volatility: 0.158, win_rate: 0.521, num_days: 754 },
    out_of_sample_benchmark_metrics: { sharpe_ratio: 0.74, cagr: 0.081, calmar_ratio: 0.49, max_drawdown: -0.165, total_return: 0.169, sortino_ratio: 0.97, volatility: 0.161, win_rate: 0.536, num_days: 754 },
    sharpe_degradation: -0.81, cagr_degradation: -0.103, calmar_degradation: -0.77,
    max_drawdown_worsening: 0.021, oos_collapsed: true,
  };
  // small IS & OOS curves
  TRAINTEST.is_curve = genCurve({ seed: 711, n: 300, drift: 0.0007, vol: 0.011 }).points;
  TRAINTEST.oos_curve = genCurve({ seed: 712, n: 150, drift: 0.0003, vol: 0.0135, crashes: [{ at: 80, depth: 0.006, width: 30 }] }).points;

  // ========================================================================
  //  WALK-FORWARD  (SmaWalkForwardResponse-ish)
  // ========================================================================
  function buildWalkForward() {
    const r = rng(808);
    const params = [[20, 90], [30, 120], [30, 120], [20, 100], [40, 150], [30, 120], [50, 200], [20, 80], [30, 130], [40, 140]];
    const windows = params.map((p, i) => {
      const trainSh = 1.1 + gauss(r) * 0.25 + 0.3;
      const testSh = trainSh - (0.4 + Math.abs(gauss(r)) * 0.4);
      return {
        window_index: i + 1,
        train_start_date: dateStr(Date.parse("2015-01-01") + i * 80 * DAY),
        test_end_date: dateStr(Date.parse("2016-06-01") + i * 80 * DAY),
        best_fast_window: p[0], best_slow_window: p[1],
        train_metrics: { sharpe_ratio: +trainSh.toFixed(2), cagr: +(0.05 + trainSh * 0.06).toFixed(3), max_drawdown: -(0.08 + r() * 0.05) },
        test_metrics: { sharpe_ratio: +testSh.toFixed(2), cagr: +(0.02 + testSh * 0.05).toFixed(3), max_drawdown: -(0.10 + r() * 0.09) },
        num_trades: Math.round(8 + r() * 8),
      };
    });
    const stitched = genCurve({ seed: 813, n: 360, drift: 0.00033, vol: 0.0118,
      crashes: [{ at: 120, depth: 0.005, width: 40 }, { at: 280, depth: 0.006, width: 45 }] });
    // Calibrate the stitched OOS curve to "degraded but still positive": a real
    // walk-forward usually underperforms the in-sample fit yet stays profitable.
    const wfRet = calibrate(stitched.dailyRet, { cagr: 0.066, sharpe: 0.74 }, 52);
    const wfBench = calibrate(stitched.benchRet, { cagr: 0.094, sharpe: 0.66 }, 52);
    const wfEq = equityFrom(wfRet), wfBe = equityFrom(wfBench);
    const wfPts = wfEq.map((p, i) => ({ date: p.date, strategy: p.strategy, benchmark: wfBe[i].strategy }));
    const uniq = new Set(params.map((p) => p.join("/"))).size;
    return {
      ticker: "SPY", start_date: "2015-01-01", end_date: "2023-12-31",
      train_window_days: 504, test_window_days: 126, step_days: 126,
      selection_metric: "sharpe_ratio",
      num_windows: windows.length, windows,
      stitched_equity_curve: wfPts,
      drawdown: drawdownSeries(wfPts),
      aggregate_metrics: metricsFrom(wfRet, wfPts.map((p) => p.strategy), 6.9),
      aggregate_benchmark_metrics: metricsFrom(wfBench, wfPts.map((p) => p.benchmark), 6.9),
      parameter_stability: {
        num_windows: windows.length, unique_parameter_sets: uniq,
        most_common_fast_window: 30, most_common_slow_window: 120, most_common_count: 3,
        parameters_unstable: uniq > windows.length / 2,
      },
    };
  }
  const WALKFWD = buildWalkForward();

  // ========================================================================
  //  PORTFOLIO / DASHBOARD aggregates
  // ========================================================================
  const PORTFOLIO = (function () {
    const agg = genCurve({ seed: 1212, n: 480, drift: 0.00252, vol: 0.0125,
      crashes: [{ at: 150, depth: 0.0070, width: 30 }, { at: 360, depth: 0.0060, width: 26 }] });
    const sRet = calibrate(agg.dailyRet, { cagr: 0.142, sharpe: 1.46 });
    const bRet = calibrate(agg.benchRet, { cagr: 0.094, sharpe: 0.66 });
    const sEq = equityFrom(sRet), bEq = equityFrom(bRet);
    const points = sEq.map((p, i) => ({ date: p.date, strategy: p.strategy, benchmark: bEq[i].strategy }));
    const m = metricsFrom(sRet, points.map((p) => p.strategy), YEARS);
    return {
      equity_curve: points,
      drawdown: drawdownSeries(points),
      metrics: m,
      nav: points[points.length - 1].strategy,
      active_strategies: STRATEGIES.length,
      total_backtests: 1287,
      cpu_load: 0.34,
    };
  })();

  // ---- Overfitting risk score (signature diagnostic) ---------------------
  // 0..100; higher = worse. Combines IS→OOS degradation + param instability +
  // sweep dispersion. Returns {score, band, factors[]}
  function overfittingScore({ degradation = 0.57, instability = 0.7, dispersion = 0.45, ddWorsen = 0.3 } = {}) {
    const score = Math.round(100 * (0.40 * degradation + 0.28 * instability + 0.20 * dispersion + 0.12 * ddWorsen));
    const band = score >= 66 ? "high" : score >= 38 ? "moderate" : "low";
    return {
      score, band,
      factors: [
        { label: "OOS Sharpe decay", value: degradation },
        { label: "Param. instability", value: instability },
        { label: "Sweep dispersion", value: dispersion },
        { label: "OOS DD worsening", value: ddWorsen },
      ],
    };
  }

  // ---- Activity feed -----------------------------------------------------
  const ACTIVITY = [
    { t: "2m", who: "you", what: "ran walk-forward on SPY", tag: "walk-forward", tone: "accent" },
    { t: "14m", who: "you", what: "saved backtest “Mom-QQQ-v3”", tag: "saved", tone: "pos" },
    { t: "1h", who: "engine", what: "flagged high overfitting risk on VOL sweep", tag: "alert", tone: "warn" },
    { t: "3h", who: "you", what: "compared 5 strategies on AAPL", tag: "compare", tone: "accent" },
    { t: "Today", who: "data", what: "refreshed OHLCV cache (yfinance)", tag: "data", tone: "mut" },
  ];

  window.QL = {
    STRATEGIES, BUILT, SWEEP, SWEEP_BEST, FAST, SLOW,
    TRAINTEST, WALKFWD, PORTFOLIO, ACTIVITY,
    overfittingScore, metricsFrom, drawdownSeries, genCurve,
  };
})();
