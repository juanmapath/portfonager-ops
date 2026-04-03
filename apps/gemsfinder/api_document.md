# GemsFinder API Documentation

This document describes the available API endpoints for the GemsFinder application. All endpoints are prefixed with `/api/gemsfinder/`.

## Base URL
`http://<your-domain>/api/gemsfinder/`

---

## 1. Tactics List
Returns a list of all defined scraping tactics, including the ID of the most recent scraping session for each.

*   **Endpoint:** `/tactics/`
*   **Method:** `GET`
*   **Authentication:** Not required (AllowAny)
*   **Response Format:**
    ```json
    [
        {
            "id": 1,
            "name": "Moonshot Small Caps",
            "active": true,
            "params": { "PEG": "u1", "ROE": "o15" },
            "market_cap_category": "small",
            "overall_weights": { "value": 0.4, "quality": 0.4, "trend": 0.2 },
            "value_weights": { "pe": 0.5, "ps": 0.5 },
            "quality_weights": { "roe": 0.7, "roa": 0.3 },
            "trend_weights": { "perf_month": 1.0 },
            "latest_session_id": 42
        }
    ]
    ```

---

## 2. Selected Assets List
Returns the assets that were ranked and selected during a specific scraping session.

*   **Endpoint:** `/assets/`
*   **Method:** `GET`
*   **Query Parameters:**
    *   `session` (required): The ID of the `ScrapingSession`.
*   **Ordering:** Automatically ordered by `score` descending (highest score first).
*   **Response Format:**
    ```json
    [
        {
            "id": 105,
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "country": "USA",
            "market_cap": "3T",
            "score": 0.925,
            "raw_metrics": {
                "pe": "28.5",
                "roe": "160%",
                "roa": "28%",
                "industry_roe_avg": "45%",
                ...
            },
            "session": 42
        }
    ]
    ```

---

## 3. Competitor Assets List
Returns the full distribution of metrics for competitors in the same industry as a selected asset.

*   **Endpoint:** `/competitors/`
*   **Method:** `GET`
*   **Query Parameters:**
    *   `target_asset` (required): The ID of the `SelectedAsset`.
*   **Response Format:**
    ```json
    [
        {
            "id": 501,
            "ticker": "MSFT",
            "company_name": "Microsoft Corporation",
            "raw_metrics": {
                "pe": "35.2",
                "roe": "38%",
                "roa": "19%",
                ...
            },
            "target_asset": 105
        }
    ]
    ```

---

## Data Structures

### Raw Metrics (JSON)
The `raw_metrics` field contains the original scraped data from Finviz. For `SelectedAsset`, it often includes comparisons to industry averages. For `CompetitorAsset`, it contains the specific metrics used to build the industry distribution.

### Weights
*   `overall_weights`: Relative importance of Value, Quality, and Trend groups.
*   `value_weights`, `quality_weights`, `trend_weights`: Importance of specific metrics within each group.
