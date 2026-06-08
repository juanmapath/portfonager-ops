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

---

## 4. Run Screener (Manual Trigger)
Manually triggers the GemsFinder screener script for all active tactics. The script runs asynchronously in the background via Django-Q so the HTTP response returns immediately.

> **⚠️ Admin only** — requires Django admin/staff credentials. Returns `403 Forbidden` for non-admin users.

*   **Endpoint:** `/run-screener/`
*   **Method:** `POST`
*   **Authentication:** Required — Django Session Auth or Basic Auth. The authenticated user **must be `is_staff = True`**.
*   **Request Body:** None required (empty POST).

### Success Response — `202 Accepted`
```json
{
    "detail": "GemsFinder screener has been queued successfully.",
    "task_id": "abc123-def456-...",
    "active_tactics": ["Ockham", "Fortress", "Moonshot"]
}
```

### Error Responses

| Status | Reason |
| :--- | :--- |
| `401 Unauthorized` | No credentials provided. |
| `403 Forbidden` | Authenticated user is not an admin/staff member. |
| `400 Bad Request` | No active tactics are configured in the database. |

### Example — cURL
```bash
curl -X POST https://<your-domain>/api/gemsfinder/run-screener/ \
  -u admin_username:admin_password
```

### Notes
- The endpoint enqueues the task via Django-Q. You can monitor progress in the **Django Admin → Django Q → Queued Tasks / Successful Tasks**.
- The screener uses a headless Selenium browser to bypass Cloudflare protection on the production server.
- Each active tactic will generate a new `ScrapingSession` record. Check the `/assets/?session=<id>` endpoint once the job completes.
