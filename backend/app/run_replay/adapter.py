"""Explicit SMA mapping. Unknown or unrepresentable settings fail closed."""
from app.annualization import resolve_annualization
from app.cost_model import resolve
from app.reproducibility import canonical_json, normalize_backtest_config
from app.schemas import BacktestRequest
from .identity import validate


def request_model(raw):
    validate(raw, limit=32768)
    if type(raw) is not dict or set(raw) - set(BacktestRequest.model_fields):
        raise ValueError("Unknown SMA request fields")
    for key in ("fast_window", "slow_window"):
        if key in raw and type(raw[key]) is not int:
            raise ValueError("SMA windows must be integers, not coerced values")
    for key in ("initial_capital", "transaction_cost_bps"):
        if key in raw and type(raw[key]) not in (int, float):
            raise ValueError("SMA amounts must be numbers, not coerced values")
    for key in ("cost_model", "position_sizing", "risk_management", "benchmark", "robustness", "sensitivity"):
        item = raw.get(key)
        if item is not None:
            annotation = BacktestRequest.model_fields[key].annotation
            from typing import get_args
            model = next(cls for cls in get_args(annotation) if hasattr(cls, "model_fields"))
            if type(item) is not dict or set(item) - set(model.model_fields):
                raise ValueError("Unknown nested SMA request fields")
            for field, value in item.items():
                if value is None or field in ("type", "mode", "ticker", "method", "metric", "x_param", "y_param"):
                    continue
                if field in ("x_values", "y_values"):
                    if type(value) is not list or any(type(v) is not int for v in value):
                        raise ValueError("Sensitivity grids require integer arrays")
                    continue
                if field == "enabled":
                    if type(value) is not bool:
                        raise ValueError("enabled must be Boolean")
                elif type(value) not in (int, float):
                    raise ValueError("Numeric options cannot be coerced")
                if field in ("lookback_days", "max_holding_days", "seed", "n_simulations", "block_size", "max_runs") and value is not None and type(value) is not int:
                    raise ValueError("Integer options cannot be coerced")
    model = BacktestRequest.model_validate(raw)
    import re
    if not model.ticker.strip() or not re.fullmatch(r"[\w .^=-]{1,80}", model.ticker):
        raise ValueError("Ticker/display label cannot contain paths or unbounded content")
    if model.benchmark and model.benchmark.mode == "custom_ticker" and not re.fullmatch(r"[\w .^=-]{1,80}", model.benchmark.ticker or ""):
        raise ValueError("Custom benchmark ticker cannot contain paths")
    if model.fast_window >= model.slow_window:
        raise ValueError("fast_window must be less than slow_window")
    from datetime import date
    if any(not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) for value in (model.start_date, model.end_date)):
        raise ValueError("SMA form dates must use YYYY-MM-DD without changing canonical identity")
    if date.fromisoformat(model.start_date) >= date.fromisoformat(model.end_date):
        raise ValueError("start_date must precede end_date")
    return model


def normalize(request, provider, fingerprint=None):
    return normalize_backtest_config(strategy="sma_crossover", ticker=request.ticker,
        start_date=request.start_date, end_date=request.end_date, initial_capital=request.initial_capital,
        strategy_params={"fast_window": request.fast_window, "slow_window": request.slow_window},
        effective_cost_bps=resolve(request.cost_model, request.transaction_cost_bps).effective_bps_per_side,
        position_sizing=request.position_sizing, risk_management=request.risk_management,
        annualization_mode_used=resolve_annualization(request.ticker, request.annualization_mode).mode_used,
        benchmark=request.benchmark, position_mode=request.position_mode, data_provider=provider,
        dataset_fingerprint=fingerprint)


def restore(config, original=None):
    if config.get("schema_version") != "backtest_config_v1" or config.get("strategy") != "sma_crossover":
        raise ValueError("This schema/strategy has no executable v1 restore adapter")
    if config.get("data_provider") not in ("yfinance", "csv_upload"):
        raise ValueError("Unsupported data source")
    if original is not None:
        request = request_model(original)
    else:
        params = config["strategy_params"]
        if set(params) != {"fast_window", "slow_window"}:
            raise ValueError("Unsupported SMA parameters")
        request = request_model({"ticker": config["ticker"], "start_date": config["start_date"],
            "end_date": config["end_date"], "initial_capital": config["initial_capital"], **params,
            "transaction_cost_bps": config["cost_model"]["effective_cost_bps"],
            "cost_model": {"type": "simple_bps", "transaction_cost_bps": config["cost_model"]["effective_cost_bps"]},
            "position_sizing": config["position_sizing"], "risk_management": config["risk_management"],
            "annualization_mode": config["annualization_mode"], "benchmark": config["benchmark"],
            "position_mode": config["position_mode"]})
    rebuilt = normalize(request, config["data_provider"], config.get("dataset_fingerprint"))
    if canonical_json(rebuilt) != canonical_json(config):
        raise ValueError("SMA configuration cannot round-trip without dropping or changing fields")
    if request.cost_model is None:
        from app.schemas import CostModel
        request.cost_model = CostModel(type="simple_bps", transaction_cost_bps=request.transaction_cost_bps)
    return request.model_dump(mode="json", exclude_none=True)
