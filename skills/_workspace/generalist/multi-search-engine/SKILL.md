---
name: "multi-search-engine"
description: "Multi search engine integration with 16 engines (7 CN + 9 Global). Supports advanced search operators, time filters, site search, privacy engines, and WolframAlpha knowledge queries. No API keys required."
---

# Multi Search Engine

Integration of 16 search engines for web crawling without API keys.

## Workflow

1. **Preparation**: AI Agent initializes an empty in-memory cookie store. Cookies are only acquired dynamically during search operations when access is denied

2. **Language Evaluation**: Detect the language attribute of the search query. If the query is in Chinese, use Domestic search engines (Baidu, Bing CN, Bing INT, 360, Sogou, WeChat, Shenma). If the query is non-Chinese, use International search engines (Google, Google HK, DuckDuckGo, Yahoo, Startpage, Brave, Ecosia, Qwant, WolframAlpha). Select engines based on query relevance and availability.

3. **Controlled Search (Reachability-first)**: Use `web_search_fast` to search and `web_fetch_clean` to read result pages:
   - Prefer `provider=auto` first (current fallback order: `official_bing/official_google(if configured) -> ddg_html -> bing_html -> ddg_api`)
   - Prefer `engine` + `site` for deterministic routing only when that engine is known reachable in current environment
   - Read details only for top 1-3 URLs using `web_fetch_clean`
   - If result pages fail with anti-bot/SSRF, switch to another source URL instead of blind retries

4. **Cookie Management**: 
   - Cookies are stored ONLY in memory during runtime
   - Cookies are acquired on-demand when search requests fail
   - No cookies are read from or written to config.json or any file
   - Cookies are cleared after search session completes
   - Only session cookies from search engine domains are captured

5. **Retry Mechanism**: If a search fails due to cookie/session issues, retry once with freshly acquired cookies after a 2-second delay

6. **Result Aggregation**: Consolidate successful results from search engines, organize and summarize them to output a core search report

## Search Engines

### Domestic (7)
- **Baidu**: `https://www.baidu.com/s?wd={keyword}`
- **Bing CN**: `https://cn.bing.com/search?q={keyword}&ensearch=0`
- **Bing INT**: `https://cn.bing.com/search?q={keyword}&ensearch=1`
- **360**: `https://www.so.com/s?q={keyword}`
- **Sogou**: `https://sogou.com/web?query={keyword}`
- **WeChat**: `https://wx.sogou.com/weixin?type=2&query={keyword}`
- **Shenma**: `https://m.sm.cn/s?q={keyword}`

### International (9)
- **Google**: `https://www.google.com/search?q={keyword}`
- **Google HK**: `https://www.google.com.hk/search?q={keyword}`
- **DuckDuckGo**: `https://duckduckgo.com/html/?q={keyword}`
- **Yahoo**: `https://search.yahoo.com/search?p={keyword}`
- **Startpage**: `https://www.startpage.com/sp/search?query={keyword}`
- **Brave**: `https://search.brave.com/search?q={keyword}`
- **Ecosia**: `https://www.ecosia.org/search?q={keyword}`
- **Qwant**: `https://www.qwant.com/?q={keyword}`
- **WolframAlpha**: `https://www.wolframalpha.com/input?i={keyword}`

## Quick Examples (Recommended)

```javascript
// Basic search (auto fallback chain)
web_search_fast({"query":"python tutorial","provider":"auto","max_results":8})

// Official Bing API
web_search_fast({"query":"latest ai policy","provider":"official_bing","max_results":8})

// Official Google Programmable Search API
web_search_fast({"query":"latest ai policy","provider":"official_google","max_results":8})

// Auto + prefer Google first among official providers
web_search_fast({"query":"latest ai policy","provider":"auto","official_provider":"google","max_results":8})

// Site-specific with deterministic engine
web_search_fast({"query":"react hooks best practices","engine":"bing","site":"github.com"})

// Domestic CN engine route
web_search_fast({"query":"人工智能 最新 进展","engine":"bing_cn","max_results":10})

// Full custom engine URL template from config
web_search_fast({"query":"privacy tools","engine_url":"https://duckduckgo.com/html/?q={keyword}"})

// Fetch details for selected result URL
web_fetch_clean({"url":"https://www.bing.com/search?q=Iran+news","max_chars":18000})

// Optional: URL-level fallback when search engines are unstable
web_fetch_clean({"url":"https://www.bing.com/search?q=site:reuters.com+iran+news"})
```

## Tool Parameters (web_search_fast)

- `query`: required search text
- `engine`: optional named engine (`bing`, `bing_cn`, `bing_int`, `ddg`, `google`, `google_hk`, `baidu`, `sogou`)
- `site`: optional domain constraint; auto-converted to `site:domain query`
- `engine_url`: optional URL template with `{keyword}`; overrides `engine`
- `provider`: fallback strategy (`auto`, `official_api`, `official_bing`, `official_google`, `ddg_api`, `ddg_html`, `bing_html`) where `auto` routes by availability first
- `official_provider`: optional preference hint for official providers (`auto`, `bing`, `google`)
- `max_results`: 1..20
- Official Bing env: `OCLAW_WEB_SEARCH_BING_API_KEY` + optional `OCLAW_WEB_SEARCH_BING_API_ENDPOINT`
- Official Google env: `OCLAW_WEB_SEARCH_GOOGLE_API_KEY` + `OCLAW_WEB_SEARCH_GOOGLE_CSE_ID` + optional `OCLAW_WEB_SEARCH_GOOGLE_API_ENDPOINT`
- Backward compatibility: legacy `OCLAW_WEB_SEARCH_OFFICIAL_API_KEY` and `OCLAW_WEB_SEARCH_OFFICIAL_API_ENDPOINT` still map to Bing official provider

## Official API Setup (Optional, can defer)

If you do not have official API keys yet, use:

```javascript
web_search_fast({"query":"latest ai policy","provider":"auto","max_results":8})
```

This will skip official providers when keys are missing and continue with HTML/API fallback.

### Bing official API (optional)

1. Create a Bing Search resource in Azure portal.
2. Open resource page and copy Key + Endpoint.
3. Set environment variables:

```powershell
$env:OCLAW_WEB_SEARCH_BING_API_KEY="your_bing_key"
$env:OCLAW_WEB_SEARCH_BING_API_ENDPOINT="https://api.bing.microsoft.com/v7.0/search"
```

### Google official API (optional)

1. Enable Google Custom Search JSON API in Google Cloud.
2. Create Programmable Search Engine and get `cx`.
3. Create API key and set environment variables:

```powershell
$env:OCLAW_WEB_SEARCH_GOOGLE_API_KEY="your_google_key"
$env:OCLAW_WEB_SEARCH_GOOGLE_CSE_ID="your_cse_id"
$env:OCLAW_WEB_SEARCH_GOOGLE_API_ENDPOINT="https://customsearch.googleapis.com/customsearch/v1"
```

### Notes

- Env vars in PowerShell apply to current shell session only.
- After changing system-level env vars, restart the runtime process.
- If official API is not configured now, keep using `provider=auto` and revisit later.

### Diagnostics in return payload
- `provider_attempts`: each attempted backend with `ok`, `count`, `elapsed_ms`, and error fields
- `error_category`: normalized failure category (`ssrf_blocked`, `anti_bot_401_403`, `timeout`, `dns_error`, `network_error`, `upstream_4xx`, `upstream_5xx`, `no_results`, `unknown_error`)

## Advanced Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `site:` | `site:github.com python` | Search within site |
| `filetype:` | `filetype:pdf report` | Specific file type |
| `""` | `"machine learning"` | Exact match |
| `-` | `python -snake` | Exclude term |
| `OR` | `cat OR dog` | Either term |

## Time Filters

| Parameter | Description |
|-----------|-------------|
| `tbs=qdr:h` | Past hour |
| `tbs=qdr:d` | Past day |
| `tbs=qdr:w` | Past week |
| `tbs=qdr:m` | Past month |
| `tbs=qdr:y` | Past year |

## Privacy Engines

- **DuckDuckGo**: No tracking
- **Startpage**: Google results + privacy
- **Brave**: Independent index
- **Qwant**: EU GDPR compliant

## Bangs Shortcuts (DuckDuckGo)

| Bang | Destination |
|------|-------------|
| `!g` | Google |
| `!gh` | GitHub |
| `!so` | Stack Overflow |
| `!w` | Wikipedia |
| `!yt` | YouTube |

## WolframAlpha Queries (Caveat)

- WolframAlpha HTML pages are often not suitable as structured answers in blocked environments.
- For deterministic math/finance/units, prefer APIs/tools that provide structured outputs.
- Use WolframAlpha URL search as a hint source, not as guaranteed machine-readable result.

## Documentation

- `references/advanced-search.md` - Domestic search guide
- `references/international-search.md` - International search guide
- `CHANGELOG.md` - Version history

## License

MIT

## Security & Privacy Notice

### Cookie Handling
- **Purpose**: Cookies are used ONLY to maintain search session state when access is denied (403/429 errors)
- **Storage**: Cookies are kept STRICTLY in memory during runtime - NEVER persisted to disk or config files
- **Acquisition**: Cookies are acquired on-demand from search engine homepages only when search requests fail
- **Scope**: Only session cookies from the specific search engine domain are captured
- **Lifecycle**: Cookies are cleared immediately after the search session completes
- **No Pre-configuration**: No cookies are loaded from config.json or any external file at startup
- **No API Keys**: This tool uses standard web search URLs, no authentication required

### Crawling Ethics
- **Rate Limiting**: Implement reasonable delays between requests (recommend 1-2 seconds)
- **Respect robots.txt**: Honor search engine crawling policies
- **Terms of Service**: Users are responsible for complying with search engine ToS
- **Purpose**: Designed for legitimate search aggregation, not mass data scraping

### Data Handling
- **No Personal Data**: Tool does not collect or transmit user personal information
- **Local Execution**: All operations run locally, no external data transmission
- **Session Isolation**: Cookies are session-specific and cleared after use
