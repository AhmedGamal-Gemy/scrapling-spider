# =============================================================================
# FILE: scrapling_spider/spider.py
# Advanced Scrapling-based spider for reconnaissance purposes
# =============================================================================

from __future__ import annotations

import asyncio
import re
import shutil
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from urllib.parse import urljoin, urlparse, urlunparse
from uuid import uuid4

from pydantic import ValidationError

# Import scrapling components with fallback for missing camoufox
try:
    from scrapling.fetchers import FetcherSession
    # Try to import StealthySession and AsyncStealthySession, but don't fail if camoufox is missing
    try:
        from scrapling.fetchers import StealthySession, AsyncStealthySession
    except (ImportError, FileNotFoundError):
        # Create dummy classes if camoufox is not available
        class StealthySession:
            pass
        class AsyncStealthySession:
            pass
except ImportError:
    # Fallback if scrapling.fetchers itself is not available
    class FetcherSession:
        pass
    class StealthySession:
        pass
    class AsyncStealthySession:
        pass

# Compatibility layer for Spider class (not available in scrapling 0.4.7)
try:
    from scrapling.spiders import Spider, Request, Response
except ImportError:
    # Create mock Spider class for compatibility
    class Spider:
        """Base spider class for compatibility."""
        name = ""
        start_urls = []
        concurrent_requests = 3
        download_delay = 0.5
        max_blocked_retries = 3
        robots_txt_obey = False
        
        def __init__(self, *args, **kwargs):
            pass
        
        def configure_sessions(self, manager):
            pass
        
        def stream(self):
            """Mock stream method."""
            return iter([])
    
    class Request:
        """Mock Request class."""
        def __init__(self, url, callback=None, sid=None, meta=None):
            self.url = url
            self.callback = callback
            self.sid = sid
            self.meta = meta or {}
    
    class Response:
        """Mock Response class."""
        def __init__(self, url="", status=200, body=None, headers=None):
            self.url = url
            self.status = status
            self.body = body or b""
            self.headers = headers or {}
            self.meta = {}

from scrapling_spider.models import (
    AdminPathType,
    AgentSuggestedAction,
    AgentInteractionMessages,
    AuthHintType,
    ChunkType,
    ConfidenceLevel,
    ContentTypeCategory,
    CrawlLifecycleEvent,
    CrawlStopReason,
    EndpointType,
    ErrorType,
    FormAnalysis,
    FormField,
    FormMethod,
    IndicatorType,
    ObservationType,
    SecurityIssue,
    SessionType,
    SpiderError,
    SpiderFinalSummary,
    SpiderPageResult,
    TechHint,
    TechSource,
    ToolResponseChunk,
)

# Guard functions and MockAgent from ai_layer_v3 (installed via pip install -e .)
try:
    from callbacks.wiring import combined_guard, MockAgent
except ImportError:
    # Try alternative import path
    from ai_layer_v3.callbacks.wiring import combined_guard, MockAgent


HEADLESS = False
MAX_CONCURRENT_SPIDERS = 3
MAX_LINKS_IN_CONTENT = 0
MAX_TECH_IN_CONTENT = 3
MAX_HEADERS_IN_CONTENT = 3

HEADER_PATTERNS: list[tuple[str, re.Pattern, TechSource]] = [
    (
        "server",
        re.compile(r"nginx|apache|iis|litespeed|cloudflare|openresty", re.I),
        TechSource.HEADER,
    ),
    ("x-powered-by", re.compile(r".+"), TechSource.HEADER),
    ("x-generator", re.compile(r".+"), TechSource.HEADER),
    ("x-aspnet-version", re.compile(r".+"), TechSource.HEADER),
    ("x-drupal-cache", re.compile(r".+"), TechSource.HEADER),
    ("x-joomla-version", re.compile(r".+"), TechSource.HEADER),
]

COOKIE_TECH_MAP: dict[str, str] = {
    "PHPSESSID": "PHP",
    "JSESSIONID": "Java",
    "ASP.NET_SessionId": ".NET",
    "laravel_session": "Laravel",
    "_rails_session": "Rails",
    "django_session": "Django",
    "wp-settings": "WordPress",
}

SCRIPT_PATTERNS: list[tuple[re.Pattern, str, ConfidenceLevel]] = [
    (re.compile(r"wp-content|wp-includes", re.I), "WordPress", ConfidenceLevel.MEDIUM),
    (re.compile(r"/sites/default/", re.I), "Drupal", ConfidenceLevel.MEDIUM),
    (re.compile(r"/components/com_", re.I), "Joomla", ConfidenceLevel.MEDIUM),
    (re.compile(r"react(\.min)?\.js", re.I), "React", ConfidenceLevel.MEDIUM),
    (re.compile(r"vue(\.min)?\.js", re.I), "Vue", ConfidenceLevel.MEDIUM),
    (re.compile(r"angular(\.min)?\.js", re.I), "Angular", ConfidenceLevel.MEDIUM),
    (re.compile(r"jquery[.-](\d[\d.]+)", re.I), "jQuery", ConfidenceLevel.MEDIUM),
]

SECURITY_HEADERS: list[str] = [
    "Content-Security-Policy",
    "Strict-Transport-Security",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
]

ADMIN_PATH_MAP: dict[str, AdminPathType] = {
    "/admin": AdminPathType.CMS_ADMIN,
    "/administrator": AdminPathType.CMS_ADMIN,
    "/wp-admin": AdminPathType.CMS_ADMIN,
    "/phpmyadmin": AdminPathType.DB_ADMIN,
    "/cpanel": AdminPathType.PANEL,
    "/plesk": AdminPathType.PANEL,
    "/dashboard": AdminPathType.DASHBOARD,
    "/manager": AdminPathType.PANEL,
    "/api/admin": AdminPathType.API_ADMIN,
}

API_URL_RE = re.compile(r"/api/|/v\d+/|/graphql|/graphiql|/wp-json/|/rest/", re.I)

AUTH_COOKIE_NAMES: set[str] = {"sessionid", "auth", "token", "jwt", "access_token"}
CSRF_FIELD_NAMES: set[str] = {"csrf", "_token", "csrftoken", "_csrf_token", "authenticity_token"}

SKIP_HREF_PREFIXES: tuple[str, ...] = (
    "mailto:",
    "tel:",
    "javascript:",
    "data:",
    "blob:",
    "#",
    "void",
)

RELEVANT_HEADER_NAMES: set[str] = {
    "server",
    "x-powered-by",
    "x-generator",
    "x-aspnet-version",
    "x-frame-options",
    "content-security-policy",
    "strict-transport-security",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
    "access-control-allow-origin",
    "www-authenticate",
    "content-type",
    "x-drupal-cache",
    "x-joomla-version",
    "upgrade",
}


class SpiderConcurrencyLimiter:
    def __init__(self, max_concurrent: int = MAX_CONCURRENT_SPIDERS):
        self._count = 0
        self._sem = asyncio.Semaphore(max_concurrent)

    async def acquire(self) -> None:
        await self._sem.acquire()
        self._count += 1

    def release(self) -> None:
        self._count -= 1
        self._sem.release()

    @property
    def active_count(self) -> int:
        return self._count


_limiter: SpiderConcurrencyLimiter | None = None


def get_scrapling_spider_concurrency_limiter() -> SpiderConcurrencyLimiter:
    global _limiter
    if _limiter is None:
        _limiter = SpiderConcurrencyLimiter()
    return _limiter or SpiderConcurrencyLimiter()


def scrapling_tool(
    url: str,
    scan_id: str = "",
    depth: int = 1,
    session_cookie: str | None = None,
    auth_header: str | None = None,
    on_page_result: Callable | None = None,
) -> str:
    if not url.startswith(("https", "http")):
        return AgentInteractionMessages.SCRAPLING_URL_INVALID.format(url=url)

    if depth not in (1, 2, 3):
        return AgentInteractionMessages.SCRAPLING_DEPTH_INVALID.format(depth=depth)

    if auth_header and session_cookie:
        return AgentInteractionMessages.SCRAPLING_BOTH_AUTH_HEADER_SESSION_COOKIE_CALLED

    try:
        with StealthySession(
            headless=HEADLESS, real_chrome=True, block_webrtc=True, solve_cloudflare=True
        ) as session:
            page = session.fetch(url=url)

        if page.status in (403, 429):
            err = SpiderError(
                error_type=ErrorType.BLOCKED if page.status == 403 else ErrorType.NETWORK,
                message=f"HTTP {page.status}",
                url=url,
                retryable=page.status == 429,
                suggested_action=AgentSuggestedAction.SWITCH_PLAYWRIGHT
                if page.status == 403
                else AgentSuggestedAction.RETRY,
            )
            return format_error(err)

        links_raw = page.css("a::attr(href)").getall()
        normalized = [_normalize_link(h, url) for h in links_raw]
        links = [link for link in normalized if link is not None]
        forms = _analyze_forms(page)
        tech = _extract_tech(page)

        cookies = getattr(page, "cookies", {}) or {}
        cookie_names = list(cookies.keys()) if isinstance(cookies, dict) else []

        result = SpiderPageResult(
            url=url,
            scan_id=scan_id,
            spider_id="sync",
            observation_hint=None,
            indicator_type=None,
            depth=0,
            page_count=1,
            status=page.status,
            content_type_category=_detect_content_type(page),
            response_size=len(page.body or b""),
            redirect_url=page.headers.get("location"),
            title=(page.css("title::text").get() or "").strip() or None,
            links=links,
            forms=forms,
            tech_hints=tech,
            relevant_headers=_filter_relevant_headers(page),
            cookie_names=cookie_names,
            security_headers_missing=_missing_security_headers(page),
            cors_wildcard=_has_cors_wildcard(page),
            auth_hint=_detect_auth_hint(page),
            endpoint_type=_detect_endpoint_type(url, page),
            is_subdomain=False,
            admin_path_type=_detect_admin_path(url),
        )

        obs_hint, ind_hint = _auto_classify(result)
        result = result.model_copy(
            update={"observation_hint": obs_hint, "indicator_type": ind_hint}
        )

        if on_page_result:
            asyncio.get_event_loop().run_until_complete(on_page_result(result))

        return format_item(result)

    except Exception as e:
        err = SpiderError(
            error_type=ErrorType.NETWORK,
            message=str(e),
            url=url,
            retryable=False,
            suggested_action=AgentSuggestedAction.DEGRADE,
        )
        return format_error(err)


META_DEPTH = "depth"
META_SPIDER_ID = "spider_id"
META_SCAN_ID = "scan_id"


def _make_recon_spider(
    seed_url: str,
    scan_id: str,
    spider_id: str,
    max_depth: int,
    max_pages: int,
    session_cookie: str | None,
    target_url: str,
    page_counter: list[int],
    page_lock: asyncio.Lock,
    redis_client=None,
    scope_allow=None,
    scope_deny=None,
) -> type:
    class ReconSpider(Spider):
        name = f"recon_{spider_id}"
        start_urls = [seed_url]
        concurrent_requests = MAX_CONCURRENT_SPIDERS * 2
        download_delay = 0.5
        max_blocked_retries = 3
        robots_txt_obey = False

        def __init__(self, *args, redis_client=None, scope_allow=None, scope_deny=None, target_url=None, **kwargs):
            super().__init__(*args, **kwargs)
            self.redis_client = redis_client
            self.scope_allow = scope_allow or []
            self.scope_deny = scope_deny or []
            self.target_url = target_url
            # Create the combined guard function with stored parameters
            if self.redis_client:
                self._guard_fn = combined_guard(
                    redis_client=self.redis_client,
                    scope_allow=self.scope_allow,
                    scope_deny=self.scope_deny,
                    target_url=self.target_url or target_url,
                    max_pages=max_pages,
                    crawl_depth=max_depth,
                    scan_id=scan_id,
                )
            else:
                self._guard_fn = None

        def configure_sessions(self, manager) -> None:
            manager.add(SessionType.FAST.value, FetcherSession(impersonate="chrome"))
            kw: dict = {"headless": HEADLESS}
            if session_cookie:
                kw["cookies"] = [{"name": "session", "value": session_cookie}]
            manager.add(SessionType.STEALTH.value, AsyncStealthySession(**kw), lazy=True)

        async def parse(self, response: Response) -> AsyncGenerator[dict | Request | ToolResponseChunk, None]:
            async with page_lock:
                current = page_counter[0]
            if current >= max_pages:
                return

            current_depth = response.meta.get(META_DEPTH, 0)

            # Guard check: current page URL
            if self._guard_fn:
                mock_tool_call = ("browser_navigate", {"url": response.url})
                mock_agent = MockAgent()
                guard_result = await self._guard_fn(mock_agent, mock_tool_call)
                if isinstance(guard_result, str):
                    yield ToolResponseChunk(
                        content=guard_result,
                        chunk_type=ChunkType.WARNING,
                        spider_id=spider_id,
                        scan_id=scan_id,
                        event=CrawlLifecycleEvent.BLOCKED,
                    )
                    return

            links_raw = response.css("a::attr(href)").getall()
            normalized = [_normalize_link(h, response.url) for h in links_raw]
            links = [link for link in normalized if link is not None]
            forms = _analyze_forms(response)
            tech = _extract_tech(response)

            yield {
                "url": response.url,
                "scan_id": scan_id,
                "spider_id": spider_id,
                "depth": current_depth,
                "page_count": current + 1,
                "status": response.status,
                "content_type_category": _detect_content_type(response),
                "response_size": len(response.body or b""),
                "redirect_url": response.headers.get("location"),
                "title": (response.css("title::text").get() or "").strip() or None,
                "links": links,
                "forms": [f.model_dump() for f in forms],
                "tech_hints": [t.model_dump() for t in tech],
                "relevant_headers": _filter_relevant_headers(response),
                "cookie_names": [],
                "security_headers_missing": _missing_security_headers(response),
                "cors_wildcard": _has_cors_wildcard(response),
                "auth_hint": _detect_auth_hint(response),
                "endpoint_type": _detect_endpoint_type(response.url, response),
                "is_subdomain": _detect_subdomain(response.url, target_url),
                "admin_path_type": _detect_admin_path(response.url),
                "observation_hint": None,
                "indicator_type": None,
            }

            if current_depth < max_depth:
                for link in links:
                    # Guard check: each link URL
                    if self._guard_fn:
                        mock_tool_call = ("browser_navigate", {"url": link})
                        mock_agent = MockAgent()
                        guard_result = await self._guard_fn(mock_agent, mock_tool_call)
                        if isinstance(guard_result, str):
                            # Blocked URL - skip, don't yield Request (Q21a: B)
                            continue

                    sid = (
                        SessionType.STEALTH.value
                        if any(p in link for p in ("/admin", "/login", "protected"))
                        else SessionType.FAST.value
                    )
                    yield Request(
                        link,
                        callback=self.parse,
                        sid=sid,
                        meta={META_DEPTH: current_depth + 1},
                    )

    return ReconSpider


class ScraplingSpider:
    name = "recon_spider"
    description = "Adaptive stealth spider for reconnaissance purposes"

    def __init__(
        self,
        on_page_result: Callable[[SpiderPageResult], Awaitable[None]] | None = None,
        session_cookie: str | None = None,
    ):
        self.on_page_result = on_page_result
        self.session_cookie = session_cookie

    async def run(
        self,
        seed_url: str,
        scan_id: str,
        max_pages: int = 3,
        max_depth: int = 1,
        checkpoint_dir: str = "./crawl_data",
        redis_client=None,
        scope_allow=None,
        scope_deny=None,
    ) -> AsyncGenerator[ToolResponseChunk, None]:
        spider_id = uuid4().hex[:6]

        if not seed_url.startswith(("http://", "https://")):
            err = SpiderError(
                error_type=ErrorType.INVALID_URL,
                message=f"bad url: {seed_url}",
                url=seed_url,
                retryable=False,
                suggested_action=AgentSuggestedAction.ABORT,
            )
            yield ToolResponseChunk(
                content=AgentInteractionMessages.SCRAPLING_URL_INVALID.format(url=seed_url),
                chunk_type=ChunkType.ERROR,
                spider_id=spider_id,
                scan_id=scan_id,
                is_error=True,
                error=err,
            )
            return

        crawl_dir = f"{checkpoint_dir}/{self.name}_{spider_id}_{scan_id}"

        limiter = getattr(self, "_limiter", get_scrapling_spider_concurrency_limiter())
        await limiter.acquire()

        page_counter: list[int] = [0]
        page_lock = asyncio.Lock()
        start_time = time.monotonic()
        stop_reason = CrawlStopReason.EXHAUSTED

        totals = {
            "links": 0,
            "forms": 0,
            "login": 0,
            "admin": 0,
            "api": 0,
            "subdomain": 0,
            "cors": 0,
        }
        all_tech: set[str] = set()
        security_issues: list[SecurityIssue] = []

        try:
            yield ToolResponseChunk(
                content=AgentInteractionMessages.SCRAPLING_LIFECYCLE.format(
                    event=CrawlLifecycleEvent.STARTED.value, sid=spider_id, scan_id=scan_id
                ),
                chunk_type=ChunkType.LIFECYCLE,
                event=CrawlLifecycleEvent.STARTED,
                spider_id=spider_id,
                scan_id=scan_id,
            )

            ReconSpider = _make_recon_spider(
                seed_url=seed_url,
                scan_id=scan_id,
                spider_id=spider_id,
                max_depth=max_depth,
                max_pages=max_pages,
                session_cookie=self.session_cookie,
                target_url=seed_url,
                page_counter=page_counter,
                page_lock=page_lock,
                redis_client=redis_client,
                scope_allow=scope_allow,
                scope_deny=scope_deny,
            )
            spider = ReconSpider(crawldir=crawl_dir)

            async for item in spider.stream():
                # Handle ToolResponseChunk items (e.g., warnings from guard checks)
                if isinstance(item, ToolResponseChunk):
                    yield item
                    continue

                # Handle dict items (normal page results) - convert to ToolResponseChunk (Q33: B)
                if not isinstance(item, dict) or "url" not in item:
                    continue

                try:
                    result = SpiderPageResult(**item)
                except ValidationError as e:
                    err = SpiderError(
                        error_type=ErrorType.VALIDATION,
                        message=str(e),
                        url=item["url"],
                        retryable=False,
                        suggested_action=AgentSuggestedAction.SKIP,
                    )
                    yield ToolResponseChunk(
                        content=format_error(err),
                        chunk_type=ChunkType.ERROR,
                        spider_id=spider_id,
                        scan_id=scan_id,
                        is_error=True,
                        error=err,
                    )
                    continue

                async with page_lock:
                    page_counter[0] += 1
                    current_count = page_counter[0]

                if current_count >= max_pages:
                    stop_reason = CrawlStopReason.MAX_PAGES
                    yield ToolResponseChunk(
                        content=format_item(result),
                        data=result,
                        chunk_type=ChunkType.PROGRESS,
                        spider_id=spider_id,
                        scan_id=scan_id,
                    )
                    break

                obs_hint, ind_hint = _auto_classify(result)
                result = result.model_copy(
                    update={
                        "observation_hint": obs_hint,
                        "indicator_type": ind_hint,
                        "page_count": current_count,
                    }
                )

                totals["links"] += result.link_count
                totals["forms"] += result.form_count
                totals["cors"] += int(result.cors_wildcard)
                totals["login"] += int(obs_hint == ObservationType.LOGIN_PAGE)
                totals["admin"] += int(obs_hint == ObservationType.ADMIN_PANEL)
                totals["api"] += int(obs_hint == ObservationType.EXPOSED_ENDPOINT)
                totals["subdomain"] += int(result.is_subdomain)
                for h in result.tech_hints:
                    all_tech.add(h.technology)

                if self.on_page_result:
                    try:
                        await self.on_page_result(result)
                    except Exception as e:
                        yield ToolResponseChunk(
                            content=AgentInteractionMessages.SCRAPLING_WARNING.format(
                                msg=f"storage error: {e}"
                            ),
                            chunk_type=ChunkType.WARNING,
                            spider_id=spider_id,
                            scan_id=scan_id,
                        )

                yield ToolResponseChunk(
                    content=format_item(result),
                    data=result,
                    chunk_type=ChunkType.PROGRESS,
                    spider_id=spider_id,
                    scan_id=scan_id,
                )

            summary = SpiderFinalSummary(
                scan_id=scan_id,
                spider_id=spider_id,
                stop_reason=stop_reason,
                total_pages=page_counter[0],
                total_links=totals["links"],
                total_forms=totals["forms"],
                login_pages_found=totals["login"],
                admin_panels_found=totals["admin"],
                api_endpoints_found=totals["api"],
                subdomains_found=totals["subdomain"],
                cors_wildcard_count=totals["cors"],
                tech_detected=sorted(all_tech),
                security_issues=security_issues,
                duration_seconds=time.monotonic() - start_time,
                checkpoint_dir=None,
            )
            yield ToolResponseChunk(
                content=format_final(summary),
                chunk_type=ChunkType.FINAL,
                spider_id=spider_id,
                scan_id=scan_id,
                is_final=True,
                final_summary=summary,
            )

        except Exception as e:
            stop_reason = CrawlStopReason.ERROR
            err = SpiderError(
                error_type=ErrorType.NETWORK,
                message=str(e),
                retryable=False,
                suggested_action=AgentSuggestedAction.DEGRADE,
                url=seed_url,
            )
            yield ToolResponseChunk(
                content=format_error(err),
                chunk_type=ChunkType.ERROR,
                spider_id=spider_id,
                scan_id=scan_id,
                is_error=True,
                error=err,
            )

        finally:
            limiter.release()
            if stop_reason != CrawlStopReason.INTERRUPTED:
                shutil.rmtree(crawl_dir, ignore_errors=True)


def _normalize_link(href: str, base_url: str) -> str | None:
    if not href or len(href) > 2048:
        return None

    href_l = href.lower().strip()
    if any(href_l.startswith(p) for p in SKIP_HREF_PREFIXES):
        return None

    absolute = urljoin(base_url, href)

    if not absolute.startswith(("http://", "https://")):
        return None

    p = urlparse(absolute)
    return urlunparse(p._replace(fragment="", path=p.path.rstrip("/") or "/"))


def _normalize_tech_name(raw: str) -> tuple[str, str | None]:
    if "/" in raw:
        name, _, version = raw.partition("/")
        return name.strip().title(), version.strip() or None
    if m := re.search(r"\s+(\d[\d.]+)$", raw):
        return raw[: m.start()].strip().title(), m.group(1)
    return raw.strip().title(), None


def _detect_content_type(response) -> ContentTypeCategory:
    ct = response.headers.get("content-type", "").lower()
    if "html" in ct:
        return ContentTypeCategory.HTML
    if "json" in ct:
        return ContentTypeCategory.JSON
    if "xml" in ct:
        return ContentTypeCategory.XML
    if response.status in (301, 302, 303, 307, 308):
        return ContentTypeCategory.REDIRECT
    return ContentTypeCategory.UNKNOWN


def _detect_endpoint_type(url: str, response) -> EndpointType:
    ct = response.headers.get("content-type", "").lower()
    url_l = url.lower()
    if "graphql" in url_l:
        return EndpointType.GRAPHQL
    if "json" in ct:
        return EndpointType.JSON_API
    if "xml" in ct:
        return EndpointType.XML
    if API_URL_RE and API_URL_RE.search(url):
        return EndpointType.REST
    if "websocket" in response.headers.get("upgrade", "").lower():
        return EndpointType.WEBSOCKET
    if "html" in ct:
        return EndpointType.HTML
    return EndpointType.UNKNOWN


def _detect_auth_hint(response) -> AuthHintType:
    www = response.headers.get("www-authenticate", "").lower()
    if response.status == 401:
        if "bearer" in www:
            return AuthHintType.BEARER_AUTH
        if "basic" in www:
            return AuthHintType.BASIC_AUTH
        return AuthHintType.REQUIRES_AUTH
    if response.status == 403:
        return AuthHintType.FORBIDDEN
    names = {c.lower() for c in response.cookies}
    if names and AUTH_COOKIE_NAMES:
        return AuthHintType.HAS_SESSION
    return AuthHintType.NONE


def _detect_admin_path(url: str) -> AdminPathType | None:
    path = urlparse(url).path.lower()
    for pattern, atype in ADMIN_PATH_MAP.items():
        if path.startswith(pattern):
            return atype
    return None


def _detect_subdomain(link_url: str, target_url: str) -> bool:
    try:
        link_host = urlparse(link_url).netloc.lower()
        target_host = urlparse(target_url).netloc.lower()
        target_root = ".".join(target_host.split(".")[-2:])
        return link_host != target_host and link_host.endswith(target_root)
    except Exception:
        return False


def _missing_security_headers(response) -> list[str]:
    present = {k.lower() for k in response.headers}
    return [h for h in SECURITY_HEADERS if h.lower() not in present]


def _has_cors_wildcard(response) -> bool:
    acao = response.headers.get("access-control-allow-origin", "")
    return acao.strip() == "*"


def _filter_relevant_headers(response) -> dict[str, str]:
    return {k.lower(): v for k, v in response.headers.items() if k.lower() in RELEVANT_HEADER_NAMES}


def _add_hint(
    hints: dict[str, TechHint], raw: str, source: TechSource, confidence: ConfidenceLevel
) -> None:
    name, version = _normalize_tech_name(raw)
    key = name.lower()
    existing = hints.get(key)
    conf_order = {ConfidenceLevel.LOW: 0, ConfidenceLevel.MEDIUM: 1, ConfidenceLevel.HIGH: 2}
    if existing is None or conf_order[confidence] > conf_order[existing.confidence]:
        hints[key] = TechHint(
            technology=name, version=version, confidence=confidence, source=source, raw_value=raw
        )


def _extract_tech(response) -> list[TechHint]:
    hints: dict[str, TechHint] = {}
    hdrs = {k.lower(): v for k, v in response.headers.items()}

    for hname, pattern, source in HEADER_PATTERNS:
        val = hdrs.get(hname, "")
        if val and pattern.search(val):
            _add_hint(hints, val, source, ConfidenceLevel.HIGH)

    for cname in response.cookies:
        tech = COOKIE_TECH_MAP.get(cname)
        if tech:
            _add_hint(hints, tech, TechSource.COOKIE, ConfidenceLevel.MEDIUM)

    for meta in response.css('meta[name="generator"]'):
        content = meta.attrib.get("content", "")
        if content:
            _add_hint(hints, content, TechSource.META, ConfidenceLevel.HIGH)

    for script in response.css("script[src]"):
        src = script.attrib.get("src", "")
        for pattern, tech, conf in SCRIPT_PATTERNS:
            if pattern.search(src):
                _add_hint(hints, tech, TechSource.SCRIPT, conf)
                break

    for link in response.css("link[rel]"):
        if "api.w.org" in link.attrib.get("rel", ""):
            _add_hint(hints, "WordPress REST API", TechSource.LINK, ConfidenceLevel.HIGH)

    return list(hints.values())


def _analyze_form(form) -> FormAnalysis:
    inputs = form.css("input")
    selects = form.css("select")
    buttons = form.css("button")
    textareas = form.css("textarea")

    input_types = [i.attrib.get("type", "text").lower() for i in inputs]
    input_names = [i.attrib.get("name", "") for i in inputs]
    input_ids = [i.attrib.get("id", "") for i in inputs]
    placeholders = [i.attrib.get("placeholder", "") for i in inputs]
    required_attrs = [i.attrib.get("required", "") for i in inputs]
    autocomplete_attrs = [i.attrib.get("autocomplete", "") for i in inputs]
    values = [i.attrib.get("value", "") for i in inputs]

    labels = []
    for i in inputs:
        label_text = ""
        input_id = i.attrib.get("id", "")
        if input_id:
            label = form.css(f"label[for='{input_id}']")
            if label:
                label_text = label[0].text or ""
        if not label_text:
            parent = i.getparent()
            if parent and parent.tag == "label":
                label_text = parent.text or ""
        labels.append(label_text.strip())

    csrf_names = [n for n in input_names if n]
    csrf_names += [s.attrib.get("name", "") for s in selects if s.attrib.get("name")]
    has_csrf = any(n.lower() in CSRF_FIELD_NAMES or "csrf" in n.lower() for n in csrf_names)
    raw_method = form.attrib.get("method", "get").upper()
    try:
        method = FormMethod(raw_method)
    except ValueError:
        method = FormMethod.GET

    all_names = list(input_names)
    all_ids = list(input_ids)
    all_types = list(input_types)
    all_placeholders = list(placeholders)
    all_required = list(required_attrs)
    all_autocomplete = list(autocomplete_attrs)
    all_values = list(values)
    all_labels = list(labels)

    for idx, sel in enumerate(selects):
        sel_name = sel.attrib.get("name", "") or f"select_{idx}"
        sel_id = sel.attrib.get("id", "")
        options = sel.css("option")
        opt_count = len(options) if options else 0
        all_names.append(sel_name)
        all_ids.append(sel_id)
        all_types.append(f"select({opt_count})")
        all_placeholders.append("")
        all_required.append(sel.attrib.get("required", ""))
        all_autocomplete.append(sel.attrib.get("autocomplete", ""))
        all_values.append("")
        all_labels.append("")

    for idx, btn in enumerate(buttons):
        btn_name = btn.attrib.get("name", "") or f"button_{idx}"
        btn_id = btn.attrib.get("id", "")
        btn_type = btn.attrib.get("type", "submit")
        btn_text = btn.text.strip() if btn.text else ""
        all_names.append(btn_name)
        all_ids.append(btn_id)
        all_types.append(f"button:{btn_type}")
        all_placeholders.append(btn_text)
        all_required.append(False)
        all_autocomplete.append("")
        all_values.append(btn.attrib.get("value", ""))
        all_labels.append("")

    for idx, ta in enumerate(textareas):
        ta_name = ta.attrib.get("name", "") or f"textarea_{idx}"
        ta_id = ta.attrib.get("id", "")
        all_names.append(ta_name)
        all_ids.append(ta_id)
        all_types.append("textarea")
        all_placeholders.append("")
        all_required.append(bool(ta.attrib.get("required", "")))
        all_autocomplete.append(ta.attrib.get("autocomplete", ""))
        all_values.append("")
        all_labels.append("")

    fields = [
        FormField(
            name=n or i or f"unnamed_{idx}",
            input_id=i,
            field_type=t,
            placeholder=p,
            label=label_val,
            required=bool(r),
            autocomplete=a,
            value=v,
        )
        for idx, (n, i, t, p, r, a, v, label_val) in enumerate(
            zip(
                all_names,
                all_ids,
                all_types,
                all_placeholders,
                all_required,
                all_autocomplete,
                all_values,
                all_labels,
                strict=True,
            )
        )
    ]

    has_password = "password" in all_types
    has_file = "file" in all_types

    return FormAnalysis(
        action=form.attrib.get("action"),
        method=method,
        has_password_field=has_password,
        has_file_upload=has_file,
        has_csrf_token=has_csrf,
        autocomplete_off=form.attrib.get("autocomplete", "").lower() == "off",
        fields=fields,
    )


def _analyze_forms(response) -> list[FormAnalysis]:
    try:
        return [_analyze_form(f) for f in response.css("form")]
    except Exception:
        return []


def _auto_classify(
    result: SpiderPageResult,
) -> tuple[ObservationType | None, IndicatorType | None]:
    if result.has_login_form:
        return ObservationType.LOGIN_PAGE, None

    if result.admin_path_type is not None:
        return ObservationType.ADMIN_PANEL, None

    if result.endpoint_type in (EndpointType.JSON_API, EndpointType.GRAPHQL, EndpointType.REST):
        return ObservationType.EXPOSED_ENDPOINT, None

    if result.is_subdomain:
        return ObservationType.SUBDOMAIN, None

    if result.cors_wildcard:
        return ObservationType.INTERESTING_SURFACE, IndicatorType.MISCONFIGURATION
    if result.security_headers_missing:
        return ObservationType.INTERESTING_SURFACE, IndicatorType.MISCONFIGURATION
    if any(f.method == FormMethod.GET and f.has_password_field for f in result.forms):
        return ObservationType.INTERESTING_SURFACE, IndicatorType.LEAKED_INFO
    if any(f.method == FormMethod.POST and not f.has_csrf_token for f in result.forms):
        return ObservationType.INTERESTING_SURFACE, IndicatorType.MISCONFIGURATION

    if result.tech_hints:
        return ObservationType.TECH_STACK, None

    return None, None


def format_item(result: SpiderPageResult) -> str:
    lines = [
        AgentInteractionMessages.SCRAPLING_PROGRESS.format(
            url=result.url, lc=result.link_count, fc=result.form_count, pc=result.page_count
        )
    ]
    if result.observation_hint:
        lines.append(
            AgentInteractionMessages.SCRAPLING_TECH_HINT.format(hint=result.observation_hint.value)
        )
    if result.tech_hints:
        tech_str = ", ".join(
            f"{h.technology} {h.version or ''}".strip()
            for h in result.tech_hints[:MAX_TECH_IN_CONTENT]
        )
        lines.append(AgentInteractionMessages.SCRAPLING_TECH.format(tech=tech_str))
    if result.security_headers_missing:
        h_str = ", ".join(result.security_headers_missing[:MAX_HEADERS_IN_CONTENT])
        lines.append(AgentInteractionMessages.SCRAPLING_HEADERS.format(headers=h_str))
    return "\n".join(lines)


def format_final(s: SpiderFinalSummary) -> str:
    return AgentInteractionMessages.SCRAPLING_FINAL.format(
        pages=s.total_pages,
        secs=s.duration_seconds,
        login=s.login_pages_found,
        api=s.api_endpoints_found,
        admin=s.admin_panels_found,
        scan_id=s.scan_id,
    )


def format_error(e: SpiderError) -> str:
    return AgentInteractionMessages.SCRAPLING_ERROR.format(etype=e.error_type.value, msg=e.message)


def format_lifecycle(event: CrawlLifecycleEvent, spider_id: str, scan_id: str) -> str:
    return AgentInteractionMessages.SCRAPLING_LIFECYCLE.format(
        event=event.value, sid=spider_id, scan_id=scan_id
    )
