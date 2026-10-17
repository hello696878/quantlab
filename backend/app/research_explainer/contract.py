"""Closed wording and presentation dictionary. No source text becomes prose."""
import re
from datetime import date, datetime
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext

from pydantic import BaseModel, ConfigDict, Field

from app.run_replay.identity import digest, validate, full_hash

SCHEMA = "research_explanation_v1"
ADAPTER = "saved_sma_v1"
POLICY = "stored_facts_policy_v1"
TEMPLATE = "saved_sma_en_v1"
LOCALE = "en-US"
# key -> original pointer, unit, presentation rule, fixed sentence prefix
FIELDS = {
    "start": ("/start_date", "date", "date", "The stored start date is"),
    "end": ("/end_date", "date", "date", "The stored end date is"),
    "capital": ("/initial_capital", "USD", "decimal_2", "The stored initial capital is"),
    "cost": ("/transaction_cost_bps", "bps_per_side", "decimal_2", "The stored one-way transaction cost is"),
    "fast": ("/params/fast_window", "observations", "integer", "The stored fast SMA window is"),
    "slow": ("/params/slow_window", "observations", "integer", "The stored slow SMA window is"),
    "total_return": ("/metrics/total_return", "decimal_return", "percent_2", "The stored total return is"),
    "cagr": ("/metrics/cagr", "decimal_return", "percent_2", "The stored CAGR is"),
    "sharpe_ratio": ("/metrics/sharpe_ratio", "ratio", "decimal_4", "The stored Sharpe ratio is"),
    "sortino_ratio": ("/metrics/sortino_ratio", "ratio", "decimal_4", "The stored Sortino ratio is"),
    "max_drawdown": ("/metrics/max_drawdown", "decimal_return", "percent_2", "The stored maximum drawdown is"),
    "volatility": ("/metrics/volatility", "decimal_return", "percent_2", "The stored annualized volatility is"),
    "calmar_ratio": ("/metrics/calmar_ratio", "ratio", "decimal_4", "The stored Calmar ratio is"),
    "win_rate": ("/metrics/win_rate", "fraction_positive_return_days", "percent_2", "The stored fraction of positive-return days is"),
    "num_days": ("/metrics/num_days", "equity_observations", "integer", "The stored equity observation count is"),
}
LIMITATIONS = {
    "scope": "This explanation describes stored values, not investment advice or a prediction.",
    "hash": "Inspection hashes check consistency, not historical authenticity or statistical validity.",
    "pinned": "This is a pinned snapshot; current source availability is not asserted after acquisition.",
    "annualization": "This adapter does not establish the annualization convention or its suitability for crypto.",
    "trades": "No total trade count is inferred from the stored trade list.",
    "legacy": "This stored record has no replay context; execution integrity remains unverified.",
    "replay": "Recorded replay material matches its internal hashes; this is not execution attestation.",
    "model": "This adapter does not verify optional lifecycle or dataset links or establish model origin.",
    "quality": "This adapter cannot interpret additional metric availability or quality flags.",
    "statistic": "A stored numeric value alone does not establish that its underlying statistic was defined.",
}
BANNED = re.compile(r"\b(buy|sell|recommend\w*|advice|predict\w*|should invest|will outperform|profitable|good|bad|robust\w*|alpha|skill|guarantee\w*|persua\w*)\b", re.I)


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    source: str
    path: str
    state: str
    value: str | int | float | None
    unit: str
    rule: str
    display: str | None


class Statement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    template_id: str
    text: str
    facts: list[str] = Field(max_length=2)
    policy_id: str | None = None


class Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: str
    adapter_version: str
    template_version: str
    policy_version: str
    locale: str
    identity: dict
    evidence: dict
    facts: list[Fact] = Field(max_length=20)
    statements: list[Statement] = Field(max_length=40)
    fingerprint: str


def pointer(parts):
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def lookup(value, path):
    if path == "":
        return True, value
    if type(path) is not str or not path.startswith("/"):
        raise ValueError("Invalid field reference")
    tokens = path[1:].split("/")
    if any(re.search(r"~(?![01])", token) for token in tokens):
        raise ValueError("Invalid field reference")
    for token in tokens:
        token = token.replace("~1", "/").replace("~0", "~")
        if type(value) is dict:
            if token not in value:
                return False, None
            value = value[token]
        elif type(value) is list:
            if not re.fullmatch(r"0|[1-9][0-9]*", token) or len(token) > 8 or int(token) >= len(value):
                return False, None
            value = value[int(token)]
        else:
            return False, None
    return True, value


def display(value, unit, rule):
    if rule == "date":
        if type(value) is not str or date.fromisoformat(value).isoformat() != value:
            raise ValueError("Invalid stored date")
        return value
    if type(value) not in (float, int):
        raise ValueError("Invalid stored numeric field")
    validate(value)
    if rule == "integer":
        if type(value) is not int or value <= 0:
            raise ValueError("Invalid stored count")
        return str(value)
    # Presentation must not depend on another caller's Decimal settings.
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN,
                              Emin=-999999, Emax=999999, capitals=1, clamp=0,
                              flags=[], traps=[])):
        number = Decimal(str(value))
        if rule == "percent_2":
            number *= 100
        precision = 4 if rule == "decimal_4" else 2
        text = format(number, f",.{precision}f")
        if value != 0 and Decimal(text.replace(",", "")) == 0:
            text = format(Decimal(str(value)) * (100 if rule == "percent_2" else 1), ".6E")
    return text + ("%" if rule == "percent_2" else " USD" if unit == "USD" else " bps" if unit == "bps_per_side" else "")


def claim_check(text):
    if text in LIMITATIONS.values():
        return
    if BANNED.search(text):
        raise ValueError("Unapproved explanatory claim")


def render(identity, evidence):
    facts, statements = [], []
    for key, (path, unit, rule, prefix) in FIELDS.items():
        source = "saved"
        if key in ("fast", "slow") and not lookup(evidence["saved"], path)[0] and "context" in evidence:
            source, path = "context", "/config/strategy_params/" + ("fast_window" if key == "fast" else "slow_window")
        exists, value = lookup(evidence[source], path)
        state = "missing" if not exists else "null" if value is None else "available"
        formatted = display(value, unit, rule) if state == "available" else None
        if key == "max_drawdown" and value is not None and value > 0:
            raise ValueError("Invalid stored drawdown sign")
        if key == "win_rate" and value is not None and not 0 <= value <= 1:
            raise ValueError("Invalid stored fraction")
        if key == "volatility" and value is not None and value < 0:
            raise ValueError("Invalid stored volatility sign")
        if key == "capital" and value is not None and value <= 0 or key == "cost" and value is not None and value < 0:
            raise ValueError("Invalid stored monetary field")
        fact = dict(id=key, source=source, path=path, state=state, value=value, unit=unit, rule=rule, display=formatted)
        facts.append(fact)
        text = f"{prefix} {formatted}." if formatted is not None else f"This stored record does not provide {key} ({state})."
        statements.append(dict(template_id=key, text=text, facts=[key], policy_id=None if formatted is not None else POLICY))
    policies = ["scope", "hash", "pinned", "annualization", "trades", "model", "statistic", "replay" if identity["trust"] == "recorded_hashes_match" else "legacy"]
    for key in policies:
        statements.append(dict(template_id=key, text=LIMITATIONS[key], facts=[], policy_id=POLICY))
    for statement in statements:
        claim_check(statement["text"])
    body = dict(schema_version=SCHEMA, adapter_version=ADAPTER, template_version=TEMPLATE,
                policy_version=POLICY, locale=LOCALE, identity=identity, evidence=evidence, facts=facts, statements=statements)
    return {**body, "fingerprint": digest(body)}


def verify(bundle):
    """Independent binding pass: closed field dictionary, exact values/types/text/hash."""
    validate(bundle, limit=64 * 1024)
    Explanation.model_validate(bundle)
    identity, evidence = bundle["identity"], bundle["evidence"]
    if set(identity) != {"source_kind", "source_schema", "saved_backtest_id", "created_at", "material_hash", "trust", "context"}:
        raise ValueError("Unapproved source identity")
    if identity["source_kind"] != "saved_backtest" or identity["source_schema"] != "saved_backtests_row_v1":
        raise ValueError("Unsupported source")
    if type(identity["saved_backtest_id"]) is not int or not 0 < identity["saved_backtest_id"] <= 2**31 - 1:
        raise ValueError("Invalid source ID")
    if type(identity["created_at"]) is not str or len(identity["created_at"]) > 40 or datetime.fromisoformat(identity["created_at"].replace("Z", "+00:00")).utcoffset() is None:
        raise ValueError("Invalid creation timestamp")
    full_hash(identity["material_hash"])
    if identity["trust"] not in ("legacy_unverified", "recorded_hashes_match"):
        raise ValueError("Unsupported trust scope")
    if set(evidence) != ({"saved", "context"} if identity["context"] is not None else {"saved"}):
        raise ValueError("Unapproved evidence source")
    if identity["context"] is not None:
        context = identity["context"]
        if type(context) is not dict or set(context) != {"id", "schema", "snapshot_hash", "result_hash", "input_hash", "execution_hash", "config_hash_full"} or context["schema"] != "replay_context_v1" or identity["trust"] != "recorded_hashes_match":
            raise ValueError("Invalid context reference")
        if type(context["id"]) is not int or not 0 < context["id"] <= 2**31 - 1:
            raise ValueError("Invalid context ID")
        for key in ("snapshot_hash", "result_hash", "input_hash", "execution_hash", "config_hash_full"):
            full_hash(context[key])
        projected = evidence["context"]
        if (context["result_hash"] != identity["material_hash"] or type(projected) is not dict
                or set(projected) != {"config"} or type(projected["config"]) is not dict
                or set(projected["config"]) != {"strategy_params"}
                or type(projected["config"]["strategy_params"]) is not dict
                or set(projected["config"]["strategy_params"]) != {"fast_window", "slow_window"}):
            raise ValueError("Invalid context projection")
    elif identity["trust"] != "legacy_unverified":
        raise ValueError("Missing integrity source")
    allowed = {"start_date", "end_date", "initial_capital", "transaction_cost_bps", "params", "metrics"}
    saved = evidence["saved"]
    if (type(saved) is not dict or set(saved) != allowed
            or type(saved["params"]) is not dict or type(saved["metrics"]) is not dict
            or set(saved["params"]) - {"fast_window", "slow_window"}
            or set(saved["metrics"]) - {k for k, v in FIELDS.items() if v[0].startswith("/metrics/")}):
        raise ValueError("Unapproved evidence field")
    if identity["context"] is not None:
        for key, value in evidence["context"]["config"]["strategy_params"].items():
            display(value, "observations", "integer")
            if key in saved["params"] and (type(saved["params"][key]) is not type(value) or saved["params"][key] != value):
                raise ValueError("Stored parameters disagree with context projection")
    expected = render(bundle["identity"], bundle["evidence"])
    if validate(bundle) != validate(expected):
        raise ValueError("Explanation bindings or content changed")
    for fact in bundle["facts"]:
        found, value = lookup(bundle["evidence"][fact["source"]], fact["path"])
        if found != (fact["state"] != "missing") or type(value) is not type(fact["value"]) or value != fact["value"]:
            raise ValueError("Unresolved field binding")
    return bundle
