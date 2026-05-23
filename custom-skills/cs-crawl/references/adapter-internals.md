# Firecrawl Adapter Internals

Source: `~/.hermes/searxng/adapter.py` (354 lines, v3)

## Architecture

This is NOT the official Firecrawl cloud API. It is a Hermes-specific adapter that
translates Firecrawl API calls to SearXNG operations + plain HTTP scraping.

```
Hermes tools (web_extract, web_search, curl)
        ↓
adapter.py (127.0.0.1:3672)  ← simulates Firecrawl API
        ↓
    ┌───────────────┐
    │ /search       │ → SearXNG (127.0.0.1:3671)
    │ /scrape       │ → requests.get + BeautifulSoup + html2text
    │ /crawl        │ → background thread BFS crawl
    │ /extract      │ → batch scrape (max 5 URLs)
    │ /map          │ → extract <a> links from page (BROKEN — often returns 0)
    └───────────────┘
```

## Scrape Pipeline (most used)

1. `requests.get(url, allow_redirects=True)` — pure HTTP, NO JS rendering
2. `BeautifulSoup(html, "html.parser")` — parse HTML
3. Remove script/style/nav/footer/header/noscript tags
4. Try to extract main content: checks `main`, `article`, `[role="main"]`,
   `.post-content`, `.article-content`, `.content`, `#content`, `#main`,
   `.markdown-body` — falls back to full page
5. `html2text` converts to markdown (ignores images, keeps links, no line wrap)
6. Truncate to 60,000 characters
7. Extract metadata: title, description (meta/og), language, finalURL
8. Extract up to 50 unique `<a href>` links (for crawl discovery)
9. Retry up to 3 times on failure, 1s between attempts

## web_extract vs Raw Firecrawl

`web_extract` (in `tools/web_tools.py`) wraps Firecrawl scrape and adds:

| Layer | What it does |
|-------|-------------|
| Security | SSRF filter (blocks private IPs), URL secret detection, website policy check |
| Scrape | Calls `_get_firecrawl_client().scrape()` — same adapter, 60s timeout |
| LLM Summary | If content > 5000 chars, sends to auxiliary model (default: gemini-3-flash-preview) for intelligent compression |
| Size handling | <5k: raw; 5k-500k: single LLM pass; 500k-2M: chunked (100k/chunk); >2M: refuse |
| Output cap | LLM output capped at 5000 chars |
| Parallelism | Multiple URLs processed in parallel via `asyncio.gather` |
| Output | Trimmed to url/title/content/error per entry |

## Known Limitations

- **No JS rendering**: Yahoo Finance, Investopedia, MarketWatch return empty/wrong content
- **No anti-bot**: Cloudflare, DataDome, CAPTCHA all block requests
- **html2text quality**: tables and complex layouts may lose structure
- **60k char cap**: long articles truncated
- **/v2/map broken**: returns 0 links for most sites — use `/v2/scrape` links field instead
- **Search quality**: SearXNG tokenization fails on financial/numeric queries

## Backend Selection (web_extract)

`_get_backend()` checks config.yaml `web.backend`, then falls back to env vars:
1. `firecrawl` — if FIRECRAWL_API_KEY or FIRECRAWL_API_URL set, or Nous gateway ready
2. `parallel` — if PARALLEL_API_KEY set
3. `tavily` — if TAVILY_API_KEY set
4. `exa` — if EXA_API_KEY set
5. Default: `firecrawl`
