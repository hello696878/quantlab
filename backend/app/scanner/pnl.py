"""The scanner's existing lag/cost convention, shared without presentation rounding."""
import numpy as np


def gross_returns_from_weights(weights: np.ndarray, returns: np.ndarray) -> np.ndarray:
    gross = np.zeros(returns.shape[0])
    gross[1:] = np.sum(weights[:-1] * returns[1:], axis=1)
    return gross


def portfolio_pnl(weights: np.ndarray, returns: np.ndarray, cost_bps: float) -> dict:
    turnover = np.zeros(returns.shape[0])
    turnover[0] = float(np.sum(np.abs(weights[0])))
    turnover[1:] = np.sum(np.abs(weights[1:] - weights[:-1]), axis=1)
    cost = turnover * (cost_bps / 1e4)
    gross = gross_returns_from_weights(weights, returns)
    net = np.zeros(returns.shape[0])
    net[1:] = gross[1:] - cost[:-1]
    return {"turnover": turnover, "cost": cost, "gross": gross, "net": net}
