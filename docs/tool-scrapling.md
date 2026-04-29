# Tool: Stealth Crawler (Scrapling)

## What This Tool Does

The stealth crawler visits web pages while avoiding detection by WAFs, bot protection, and rate limiters. It mimics real browser behavior (headers, timing, fingerprints) to blend in with normal traffic.

---

## Normal Behavior

- When given a URL, it should crawl the page and return discovered links, forms, and page titles
- It should follow links up to the specified depth (1 = single page, 2 = one hop, 3 = two hops)
- It should avoid detection by rotating headers, adding realistic delays, and mimicking browser fingerprints

### Example
> Write an example of a normal stealth crawl. What URL, what depth, what gets discovered?

---

## Edge Cases

- What if the target has CAPTCHA protection?
- What if the target rate-limits after 10 requests?
- What if the target blocks known crawler user-agents?
- What if the target uses Cloudflare Bot Management or similar?
- What if the target returns different content based on geolocation?
- What if the target's robots.txt disallows crawling?

---

## Failure / Fallback

- If the crawler gets a 429 (rate limit), should it back off and retry? How many times?
- If the crawler gets a 403 (forbidden), should it try with different headers or give up?
- If the crawler is completely blocked, should ReconAgent continue with browser + search?
- What if the crawler discovers a link that the browser tool should visit instead?

---

## Security-Specific

- Can the stealth crawler be detected and logged by the target's security team? Should we care?
- What if the crawler discovers a hidden path (not linked from the main page) — is that an observation?
- What if the crawler finds a directory listing (e.g., `/backup/` showing files)?
- Should the crawler attempt to access common sensitive paths (`/.env`, `/wp-config.php`, `/.git/`)?
- What if the crawler finds a page that leaks internal IP addresses or server info?

---

## Output Validation

### A GOOD Crawl Result Looks Like:
> Describe what useful crawl output looks like.

### A BAD Crawl Result Looks Like:
> Describe what useless crawl output looks like.

### Must Always Include:
- [ ] List of discovered URLs
- [ ] HTTP status code for each URL
- [ ] Page title for each URL
- [ ] Number of forms discovered
- [ ] Whether the crawl was blocked or completed successfully
