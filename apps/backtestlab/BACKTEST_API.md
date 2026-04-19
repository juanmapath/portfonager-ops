# Backtest Results API Integration Guide

This guide describes how to consume the Backtest Results API for use in a web application.

## Endpoints

### 1. List/Filter Backtest Results
**Endpoint:** `GET /api/backtestlab/results/`

**Query Parameters:**
- `bot_asset`: Filter by `BotAsset` ID (e.g., `?bot_asset=13`)
- `period`: Filter by period (e.g., `?period=1y`, `?period=all`, `?period=1q`)

**Example Request:**
`GET http://localhost:8000/api/backtestlab/results/?bot_asset=13&period=1y`

### 2. Retrieve Specific Result
**Endpoint:** `GET /api/backtestlab/results/{id}/`

---

## Data Structure Example

```json
{
  "id": 105,
  "bot_asset": 13,
  "period": "1q",
  "created_at": "2026-04-18T04:50:15.123Z",
  "metrics": {
    "start": "2026-01-15T00:00:00",
    "end": "2026-04-17T00:00:00",
    "BH_rets": 21.8,
    "BH_rets_EA": 21.8,
    "ST_rets": -20.27,
    "ST_rets_EA": -20.27,
    "CAGR": -20.27,
    "max_dd": 7.31,
    "profit_factor": 0.45,
    "no_trds": 4,
    "prof_trds": 75.0,
    "adj_rets": -9.72
    // ... other statistical scalars
  },
  "distributions": {
    "longs_rets": [0.01, -0.04, 0.02, 0.01],
    "short_rets": [],
    "days_inside": [5, 4, 6, 5],
    "bootstrap": {
      "confidence_interaval_30": [-0.01, 0.01],
      "estadisticas_bootstrap_ci": [0.005, -0.002, ...],
      "statistic_of_back_test": -0.038
      // ... bootstrap result arrays
    }
  },
  "equity_curve": {
    "Date": ["2026-01-15", "2026-01-16", ...],
    "cum_returns_st": [0.0, 0.12, -0.05, ...]
  },
  "bh_curve": {
    "Date": ["2026-01-15", "2026-01-16", ...],
    "BH_rets": [0.0, 0.05, 0.10, ...]
  },
  "drawdown_curve": {
    "Date": ["2026-01-15", "2026-01-16", ...],
    "drawdown": [0.0, 0.0, 1.2, ...]
  }
}
```

## Plotting Recommendations

1. **Equity Curve:** Use `equity_curve` vs `bh_curve` (Buy & Hold) in a time-series line chart.
2. **Drawdown:** Use `drawdown_curve` in an area chart (usually inverted).
3. **Trade Distributions:** Use `distributions.longs_rets` and `distributions.short_rets` to build histograms of returns per trade.
4. **Bootstrap H0:** Plot `distributions.bootstrap.estadisticas_bootstrap_h0` as a histogram to show the null hypothesis vs `statistic_of_back_test`.
