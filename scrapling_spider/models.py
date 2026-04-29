from __future__ import annotations

from enum import StrEnum, auto
from dataclasses import dataclass

from pydantic import Field, BaseModel, computed_field


class ObservationType(StrEnum):
    LOGIN_PAGE = auto()
    ADMIN_PANEL = auto()
    EXPOSED_ENDPOINT = auto()
    TECH_STACK = auto()
    SUBDOMAIN = auto()
    INTERESTING_SURFACE = auto()


class IndicatorType(StrEnum):
    SENSITIVE_KEYWORD = auto()
    UNUSUAL_RESPONSE = auto()
    HIDDEN_PATH = auto()
    LEAKED_INFO = auto()
    MISCONFIGURATION = auto()
    OTHER = auto()


class ConfidenceLevel(StrEnum):
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()


class ChunkType(StrEnum):
    LIFECYCLE = auto()
    PROGRESS = auto()
    FINAL = auto()
    ERROR = auto()
    WARNING = auto()


class CrawlStopReason(StrEnum):
    MAX_PAGES = auto()
    EXHAUSTED = auto()
    ERROR = auto()
    INTERRUPTED = auto()
    SCOPE_BLOCKED = auto()


class CrawlLifecycleEvent(StrEnum):
    STARTED = auto()
    PAGE_CRAWLED = auto()
    BLOCKED = auto()
    PAUSED = auto()
    RESUMED = auto()
    COMPLETED = auto()
    FAILED = auto()


class ErrorType(StrEnum):
    VALIDATION = auto()
    NETWORK = auto()
    BLOCKED = auto()
    TIMEOUT = auto()
    PARSE = auto()
    INVALID_URL = auto()
    STORAGE = auto()


class TechSource(StrEnum):
    HEADER = auto()
    META = auto()
    SCRIPT = auto()
    COOKIE = auto()
    LINK = auto()
    CONTENT = auto()
    URL = auto()


class ContentTypeCategory(StrEnum):
    HTML = auto()
    JSON = auto()
    XML = auto()
    BINARY = auto()
    TEXT = auto()
    REDIRECT = auto()
    UNKNOWN = auto()


class FormMethod(StrEnum):
    GET = auto()
    POST = auto()
    PUT = auto()
    DELETE = auto()
    PATCH = auto()


class AuthHintType(StrEnum):
    REQUIRES_AUTH = auto()
    FORBIDDEN = auto()
    HAS_SESSION = auto()
    BASIC_AUTH = auto()
    BEARER_AUTH = auto()
    NONE = auto()


class EndpointType(StrEnum):
    HTML = auto()
    JSON_API = auto()
    XML = auto()
    GRAPHQL = auto()
    REST = auto()
    WEBSOCKET = auto()
    UNKNOWN = auto()


class SessionType(StrEnum):
    FAST = auto()
    STEALTH = auto()


class SpiderMeta(StrEnum):
    DEPTH = auto()
    SPIDER_ID = auto()
    SCAN_ID = auto()
    SESSION = auto()


class SecurityIssueType(StrEnum):
    MISSING_CSP = auto()
    MISSING_HSTS = auto()
    MISSING_XFRAME = auto()
    CORS_WILDCARD = auto()
    PASSWORD_IN_GET = auto()
    CSRF_MISSING = auto()
    OTHER = auto()


class AdminPathType(StrEnum):
    CMS_ADMIN = auto()
    DB_ADMIN = auto()
    PANEL = auto()
    DASHBOARD = auto()
    API_ADMIN = auto()
    OTHER = auto()


class AgentSuggestedAction(StrEnum):
    SWITCH_PLAYWRIGHT = auto()
    RETRY = auto()
    SKIP = auto()
    ABORT = auto()
    DEGRADE = auto()


class FormField(BaseModel):
    name: str = ""
    input_id: str = ""
    field_type: str = "text"
    placeholder: str = ""
    label: str = ""
    required: bool = False
    autocomplete: str = ""
    value: str = ""


class FormAnalysis(BaseModel):
    action: str | None = None
    method: FormMethod = FormMethod.GET
    has_password_field: bool = False
    fields: list[FormField] = Field(default_factory=list)
    has_file_upload: bool = False
    has_csrf_token: bool = False
    autocomplete_off: bool = False

    @computed_field
    @property
    def field_count(self) -> int:
        return len(self.fields)


class TechHint(BaseModel):
    technology: str
    version: str | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    source: TechSource = TechSource.CONTENT
    raw_value: str = ""


class SecurityIssue(BaseModel):
    issue_type: SecurityIssueType
    description: str | None = None


class SpiderPageResult(BaseModel):
    url: str
    scan_id: str
    spider_id: str
    depth: int
    page_count: int
    status: int
    content_type_category: ContentTypeCategory
    response_size: int
    redirect_url: str | None
    title: str | None
    links: list[str]
    forms: list[FormAnalysis]
    tech_hints: list[TechHint]
    relevant_headers: dict[str, str]
    cookie_names: list[str]
    security_headers_missing: list[str]
    cors_wildcard: bool
    auth_hint: AuthHintType
    endpoint_type: EndpointType
    is_subdomain: bool
    admin_path_type: AdminPathType | None
    observation_hint: ObservationType | None
    indicator_type: IndicatorType | None

    @computed_field
    @property
    def link_count(self) -> int:
        return len(self.links)

    @computed_field
    @property
    def form_count(self) -> int:
        return len(self.forms)

    @computed_field
    @property
    def has_login_form(self) -> bool:
        for form in self.forms:
            if form.has_password_field == True:
                return True
        return False


class SpiderFinalSummary(BaseModel):
    scan_id: str
    spider_id: str
    stop_reason: CrawlStopReason = CrawlStopReason.EXHAUSTED
    total_pages: int = 0
    total_links: int = 0
    total_forms: int = 0
    login_pages_found: int = 0
    admin_panels_found: int = 0
    api_endpoints_found: int = 0
    subdomains_found: int = 0
    cors_wildcard_count: int = 0
    tech_detected: list[str] = Field(default_factory=list)
    security_issues: list[SecurityIssue] = Field(default_factory=list)
    duration_seconds: float = 0.0
    checkpoint_dir: str | None = None


class SpiderError(BaseModel):
    url: str
    error_type: ErrorType
    message: str
    retryable: bool = False
    suggested_action: AgentSuggestedAction = AgentSuggestedAction.SKIP


@dataclass
class ToolResponseChunk:
    content: str
    data: SpiderPageResult | None = None
    chunk_type: ChunkType = ChunkType.PROGRESS
    spider_id: str = ""
    scan_id: str = ""
    event: CrawlLifecycleEvent | None = None
    is_final: bool = False
    is_error: bool = False
    error: SpiderError | None = None
    final_summary: SpiderFinalSummary | None = None


class AgentInteractionMessages(StrEnum):
    SCRAPLING_PROGRESS = "Crawled {url} — found {lc} links, {fc} forms [page {pc}]"
    SCRAPLING_TECH_HINT = "→ {hint} detected"
    SCRAPLING_TECH = "Tech: {tech}"
    SCRAPLING_HEADERS = "Missing headers: {headers}"
    SCRAPLING_FINAL = "Done. {pages} pages in {secs:.1f}s. {login} login, {api} api, {admin} admin. scan_id={scan_id}"
    SCRAPLING_ERROR = "error:{etype} {msg}"
    SCRAPLING_URL_INVALID = "invalid seed_url: {url}"
    SCRAPLING_DEPTH_INVALID = "Invalid depth '{depth}' should be on of these values (1,2,3) "
    SCRAPLING_WARNING = "warning: {msg}"
    SCRAPLING_LIFECYCLE = "spider {event}: {sid} scan={scan_id}"
    SCRAPLING_BOTH_AUTH_HEADER_SESSION_COOKIE_CALLED = "Invalid: cannot use both paramaters 'auth_header', 'session_cookie'. only one should be called"
