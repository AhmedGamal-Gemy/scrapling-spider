# scrapling-spider

Advanced Scrapling-based stealth spider for reconnaissance purposes.

## Description

An adaptive stealth web crawler that mimics real browser behavior to avoid detection by WAFs, bot protection, and rate limiters. Used for web reconnaissance during penetration testing.

## Installation

```bash
uv add scrapling-spider@file://./scrapling-spider
```

Or for development:

```bash
cd scrapling-spider
uv pip install -e .
```

## Demo

Install demo dependencies and run the Streamlit UI:

```bash
cd scrapling-spider
uv pip install -e ".[demo]"
streamlit run demo/app.py
```

## Quick Usage

```python
from scrapling_spider import ScraplingSpider, scrapling_tool

# Sync single-page crawl
result = scrapling_tool(
    url="https://example.com",
    scan_id="scan-001",
    depth=1
)
print(result)

# Async long-running spider
import asyncio

async def crawl():
    spider = ScraplingSpider()
    async for chunk in spider.run(
        seed_url="https://example.com",
        scan_id="scan-002",
        max_pages=10,
        max_depth=2
    ):
        print(chunk.content)

asyncio.run(crawl())
```

## Features

- Stealth crawling with anti-detection
- Form detection and analysis
- Technology fingerprinting
- Security header analysis
- Login page detection
- Admin panel discovery
- API endpoint detection
- Real-time streaming progress

