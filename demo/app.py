import asyncio
import threading
import time

import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

from scrapling_spider import ScraplingSpider, SpiderPageResult, SpiderFinalSummary, ChunkType

st.set_page_config(page_title="🕷️ Spider UI", page_icon="🕷️", layout="wide")

st.markdown(
    """
<style>
    @keyframes spiderLegs {
        0%, 100% { content: "🕷️"; }
        25% { content: "🕷️"; }
        50% { content: "🕷️"; }
        75% { content: "🕷️"; }
    }
    @keyframes spiderWalk {
        0% { transform: translate(-50%, -50%) translateX(0) rotate(0deg); }
        25% { transform: translate(-50%, -50%) translateX(25%) rotate(-5deg); }
        50% { transform: translate(-50%, -50%) translateX(50%) rotate(0deg); }
        75% { transform: translate(-50%, -50%) translateX(75%) rotate(5deg); }
        100% { transform: translate(-50%, -50%) translateX(0) rotate(0deg); }
    }
    @keyframes spiderPulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.15); }
    }
    @keyframes webPulse {
        0%, 100% { opacity: 0.2; }
        50% { opacity: 0.5; }
    }
    @keyframes progressGlow {
        0%, 100% { box-shadow: 0 0 10px rgba(76, 175, 80, 0.5); }
        50% { box-shadow: 0 0 25px rgba(76, 175, 80, 0.9); }
    }
    .spider-progress-container {
        position: relative;
        height: 50px;
        background: linear-gradient(90deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 25px;
        overflow: hidden;
        margin: 10px 0;
    }
    .spider-web {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-image:
            radial-gradient(circle at 50% 50%, transparent 2px, #4a5568 2px);
        background-size: 20px 20px;
        animation: webPulse 2s ease-in-out infinite;
    }
    .spider-progress-fill {
        position: absolute;
        top: 0;
        left: 0;
        height: 100%;
        background: linear-gradient(90deg, #4CAF50, #8BC34A);
        border-radius: 25px;
        transition: width 0.3s ease;
        animation: progressGlow 1.5s ease-in-out infinite;
    }
    .spider-icon {
        position: absolute;
        top: 50%;
        left: 0;
        font-size: 28px;
        z-index: 10;
    }
    .spider-icon.crawling {
        animation: spiderWalk 2s ease-in-out infinite;
    }
    .chunk-card {
        padding: 15px;
        border-radius: 12px;
        margin: 10px 0;
        border-left: 6px solid;
        transition: all 0.3s ease;
    }
    .chunk-card:hover {
        transform: translateX(5px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .chunk-lifecycle {
        background: linear-gradient(135deg, #e3f2fd, #bbdefb);
        border-color: #2196F3;
    }
    .chunk-progress {
        background: linear-gradient(135deg, #e8f5e9, #c8e6c9);
        border-color: #4CAF50;
    }
    .chunk-warning { background: linear-gradient(135deg, #fff3e0, #ffe0b2); border-color: #FF9800; }
    .chunk-error { background: linear-gradient(135deg, #ffebee, #ffcdd2); border-color: #f44336; }
    .chunk-final { background: linear-gradient(135deg, #f3e5f5, #e1bee7); border-color: #9C27B0; }
    .form-card {
        background: #f5f5f5;
        border-radius: 8px;
        padding: 10px;
        margin: 5px 0;
        font-size: 12px;
    }
    .header-badge {
        display: inline-block;
        background: #2196F3;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        margin: 2px;
    }
    .tech-badge {
        display: inline-block;
        background: #FF9800;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        margin: 2px;
    }
    .status-box {
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        margin: 10px 0;
    }
    .status-crawling {
        background: linear-gradient(135deg, #11998e, #38ef7d);
        color: white;
        animation: spiderPulse 1s ease-in-out infinite;
    }
    .status-done { background: linear-gradient(135deg, #2196F3, #03A9F4); color: white; }
    .status-stopped { background: linear-gradient(135deg, #FF9800, #FFC107); color: white; }
    .status-ready { background: linear-gradient(135deg, #9E9E9E, #BDBDBD); color: white; }
    .detail-section {
        background: #fafafa;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
    }
    .code-preview {
        background: #1e1e1e;
        color: #d4d4d4;
        padding: 10px;
        border-radius: 6px;
        font-family: 'Consolas', monospace;
        font-size: 11px;
        max-height: 200px;
        overflow: auto;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title("🕷️ Scrapling Spider")

with st.sidebar:
    st.header("⚙️ Crawl Settings")
    seed_url = st.text_input("🌐 Seed URL", value="https://books.toscrape.com")
    scan_id = st.text_input("🔖 Scan ID", value="test-001")
    max_pages = st.slider("📄 Max Pages", 1, 100, 10)
    max_depth = st.slider("📊 Max Depth", 1, 5, 2)
    checkpoint_dir = st.text_input("📁 Checkpoint Dir", value="./crawl_data")

    st.divider()
    st.header("🔄 Live Settings")
    auto_refresh = st.checkbox("Auto-refresh", value=True)
    refresh_interval = st.slider("Refresh interval (s)", 0.5, 5.0, 0.5, 0.5)
    show_details = st.checkbox("Show full details", value=True)
    show_response = st.checkbox("Show response preview", value=False)

    st.divider()
    st.markdown(
        "**About:** Adaptive stealth spider for reconnaissance. Part of [Inspect v3](https://github.com/anomalyco/inspect)"
    )
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        start_btn = st.button("▶️ Start", type="primary", use_container_width=True)
    with col_btn2:
        stop_btn = st.button("⏹️ Stop", use_container_width=True)

if "chunks" not in st.session_state:
    st.session_state.chunks = []
if "stats" not in st.session_state:
    st.session_state.stats = {"pages": 0, "links": 0, "forms": 0, "tech": [], "security": []}
if "summary" not in st.session_state:
    st.session_state.summary = None
if "crawl_done" not in st.session_state:
    st.session_state.crawl_done = False
if "crawl_active" not in st.session_state:
    st.session_state.crawl_active = False
if "stop_event" not in st.session_state:
    st.session_state.stop_event = None
if "current_url" not in st.session_state:
    st.session_state.current_url = ""


def get_chunk_class(chunk_type: ChunkType) -> str:
    classes = {
        ChunkType.LIFECYCLE: "chunk-lifecycle",
        ChunkType.PROGRESS: "chunk-progress",
        ChunkType.WARNING: "chunk-warning",
        ChunkType.ERROR: "chunk-error",
        ChunkType.FINAL: "chunk-final",
    }
    return classes.get(chunk_type, "")


def format_chunk_detail(chunk, show_response=False) -> str:
    if chunk.chunk_type == ChunkType.PROGRESS and chunk.data:
        data: SpiderPageResult = chunk.data
        details = []

        details.append("### 🌐 Page Info")
        details.append(f"**URL:** `{data.url}`")
        details.append(f"**Status:** {data.status}")
        details.append(f"**Title:** {data.title or 'N/A'}")
        details.append(f"**Depth:** {data.depth}")
        details.append(f"**Response Size:** {data.response_size:,} bytes")

        details.append(f"\n### 🔗 Links ({len(data.links)})")
        if data.links:
            details.append(", ".join([f"`{link}`" for link in data.links[:10]]))
            if len(data.links) > 10:
                details.append(f"... and {len(data.links) - 10} more")

        details.append(f"\n### 📝 Forms ({len(data.forms)})")
        for i, form in enumerate(data.forms[:5]):
            form_method = form.method.value.upper()
            form_action = f" → `{form.action}`" if form.action else ""
            form_flags = []
            if form.has_password_field:
                form_flags.append("🔐")
            if form.has_file_upload:
                form_flags.append("📎")
            if form.has_csrf_token:
                form_flags.append("🛡️ CSRF")
            flags_str = " ".join(form_flags)

            details.append(f"\n**Form {i + 1}:** {form_method}{form_action} {flags_str}")
            for field in form.fields:
                type_badge = f"`{field.field_type}`" if field.field_type != "text" else ""
                req_badge = "**(required)**" if field.required else ""
                placeholder_info = f'placeholder="{field.placeholder}"' if field.placeholder else ""
                label_info = f'label="{field.label}"' if field.label else ""
                autocomplete_info = f'auto="{field.autocomplete}"' if field.autocomplete else ""

                field_desc_parts = [
                    p for p in [placeholder_info, label_info, autocomplete_info] if p
                ]
                field_desc = " | ".join(field_desc_parts)

                details.append(f"  - `{field.name}` {type_badge} {req_badge} {field_desc}")

        if data.tech_hints:
            details.append("\n### 🛠️ Technologies Detected")
            tech_names = [t.technology for t in data.tech_hints if t.technology]
            if tech_names:
                for t in tech_names:
                    details.append(f"- `{t}`")

        if data.security_headers_missing:
            details.append("\n### 🔒 Missing Security Headers")
            for h in data.security_headers_missing:
                details.append(f"- `{h}`")

        if data.cors_wildcard:
            details.append("\n⚠️ **CORS Wildcard detected!**")

        if data.auth_hint and data.auth_hint.value != "none":
            details.append(f"\n🔐 **Auth Hint:** {data.auth_hint.value}")

        if data.endpoint_type and data.endpoint_type.value != "html":
            details.append(f"\n📡 **Endpoint Type:** {data.endpoint_type.value}")

        if data.relevant_headers:
            details.append("\n### 📋 Relevant Headers")
            for k, v in data.relevant_headers.items():
                details.append(f"- `{k}`: `{v}`")

        return "\n".join(details)
    elif chunk.chunk_type == ChunkType.LIFECYCLE:
        return f"### 🔵 Lifecycle Event\n**Event:** {chunk.event.value if chunk.event else 'N/A'}"
    elif chunk.chunk_type == ChunkType.ERROR and chunk.error:
        url = chunk.error.url or "N/A"
        err_type = chunk.error.error_type.value
        return f"### ❌ Error\n**Type:** {err_type}\n**Message:** {chunk.error.message}\n**URL:** {url}"
    elif chunk.chunk_type == ChunkType.FINAL and chunk.final_summary:
        sm = chunk.final_summary
        return f"""### 🏁 Final Summary
**Scan ID:** {sm.scan_id}
**Spider ID:** {sm.spider_id}
**Duration:** {sm.duration_seconds:.2f}s
**Total Pages:** {sm.total_pages}
**Total Links:** {sm.total_links}
**Total Forms:** {sm.total_forms}
**Login Pages:** {sm.login_pages_found}
**API Endpoints:** {sm.api_endpoints_found}
**Admin Panels:** {sm.admin_panels_found}"""
    return ""


def crawl_worker(seed_url, scan_id, max_pages, max_depth, checkpoint_dir, stop_event):
    tool = ScraplingSpider()

    async def stream_and_store():
        try:
            async for chunk in tool.run(
                seed_url=seed_url,
                scan_id=scan_id,
                max_pages=max_pages,
                max_depth=max_depth,
                checkpoint_dir=checkpoint_dir,
            ):
                if stop_event and stop_event.is_set():
                    break

                st.session_state.chunks.insert(0, chunk)

                if chunk.chunk_type == ChunkType.PROGRESS and chunk.data:
                    data: SpiderPageResult = chunk.data
                    st.session_state.current_url = data.url
                    st.session_state.stats["pages"] += 1
                    st.session_state.stats["links"] += len(data.links)
                    st.session_state.stats["forms"] += len(data.forms)

                    for t in data.tech_hints:
                        if t.technology and t.technology not in st.session_state.stats["tech"]:
                            st.session_state.stats["tech"].append(t.technology)

                    if data.security_headers_missing:
                        st.session_state.stats["security"].append(
                            {"url": data.url, "missing": data.security_headers_missing}
                        )

                    await asyncio.sleep(0.3)

                if chunk.is_final and chunk.final_summary:
                    st.session_state.summary = chunk.final_summary
                    st.session_state.crawl_done = True
                    st.session_state.crawl_active = False
        except asyncio.CancelledError:
            st.session_state.crawl_done = True
            st.session_state.crawl_active = False
        except Exception as e:
            st.session_state.error = str(e)
            st.session_state.crawl_active = False

    asyncio.run(stream_and_store())


if start_btn and not st.session_state.crawl_active:
    st.session_state.chunks = []
    st.session_state.stats = {"pages": 0, "links": 0, "forms": 0, "tech": [], "security": []}
    st.session_state.summary = None
    st.session_state.crawl_done = False
    st.session_state.crawl_active = True
    st.session_state.error = None
    st.session_state.current_url = ""

    stop_event = threading.Event()
    st.session_state.stop_event = stop_event

    thread = threading.Thread(
        target=crawl_worker,
        args=(seed_url, scan_id, max_pages, max_depth, checkpoint_dir, stop_event),
        daemon=True,
    )
    add_script_run_ctx(thread)
    thread.start()

if stop_btn and st.session_state.crawl_active:
    if st.session_state.stop_event:
        st.session_state.stop_event.set()
    st.session_state.crawl_active = False
    st.rerun()

col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("🕸️ Crawl Log")

    # Show final summary at top if crawl is done
    if st.session_state.summary:
        st.success("🏁 Scan Complete!")

        sm: SpiderFinalSummary = st.session_state.summary

        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            st.metric("📄 Pages", sm.total_pages)
        with col_s2:
            st.metric("🔗 Links", sm.total_links)
        with col_s3:
            st.metric("📝 Forms", sm.total_forms)
        with col_s4:
            st.metric("⏱️ Duration", f"{sm.duration_seconds:.1f}s")

        col_s5, col_s6, col_s7 = st.columns(3)
        with col_s5:
            st.metric("🔐 Login", sm.login_pages_found)
        with col_s6:
            st.metric("📡 API", sm.api_endpoints_found)
        with col_s7:
            st.metric("🛡️ Admin", sm.admin_panels_found)

        if sm.tech_detected:
            st.write("**🛠️ Tech:** " + ", ".join(f"`{t}`" for t in sm.tech_detected[:10]))

        # Export button
        if st.session_state.chunks:
            import json

            export_data = []
            for chunk in st.session_state.chunks:
                if chunk.data:
                    export_data.append(chunk.data.model_dump())

            if export_data:
                export_json = json.dumps(export_data, indent=2, default=str)
                st.download_button(
                    label="📥 Export JSON",
                    data=export_json,
                    file_name=f"crawl_{scan_id}.json",
                    mime="application/json",
                )

        st.divider()

    if st.session_state.crawl_active:
        progress_pct = min((st.session_state.stats["pages"] / max_pages) * 100, 100)
        spider_pos = f"{progress_pct}%"

        st.markdown(
            f"""
        <div class="spider-progress-container">
            <div class="spider-web"></div>
            <div class="spider-progress-fill" style="width: {spider_pos};"></div>
            <div class="spider-icon crawling" style="left: {spider_pos};">🕷️</div>
        </div>
        <div style="text-align: center; color: #666;">
            🕷️ Crawling: <code>{st.session_state.current_url[:60]}</code>
        </div>
        """,
            unsafe_allow_html=True,
        )

    if st.session_state.chunks:
        total_chunks = len(st.session_state.chunks)

        col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
        with col_p1:
            st.write(f"**Total: {total_chunks} chunks**")
        with col_p2:
            chunks_per_page = st.selectbox(
                "Chunks per page",
                options=[5, 10, 20, 50, 100],
                index=1,
                key="chunks_per_page",
            )
        with col_p3:
            total_pages = max(1, (total_chunks + chunks_per_page - 1) // chunks_per_page)
            page = st.number_input(
                f"Page (of {total_pages})",
                min_value=1,
                max_value=total_pages,
                value=1,
                key="chunk_page",
            )

        start_idx = (page - 1) * chunks_per_page
        end_idx = start_idx + chunks_per_page
        page_chunks = st.session_state.chunks[start_idx:end_idx]

        for chunk in page_chunks:
            if chunk.chunk_type == ChunkType.FINAL and chunk.final_summary:
                st.success(f"🏁 **{chunk.content}**")
            elif chunk.chunk_type == ChunkType.LIFECYCLE:
                st.info(f"🔵 {chunk.content}")
            elif chunk.chunk_type == ChunkType.WARNING:
                st.warning(f"⚠️ {chunk.content}")
            elif chunk.chunk_type == ChunkType.ERROR:
                st.error(f"❌ {chunk.content}")
            else:
                chunk_class = get_chunk_class(chunk.chunk_type)
                st.markdown(
                    f"""
                <div class="chunk-card {chunk_class}">
                    <strong>✅ {chunk.chunk_type.value.upper()}</strong> — {chunk.content}
                </div>
                """,
                    unsafe_allow_html=True,
                )

            if show_details and chunk.chunk_type not in [ChunkType.LIFECYCLE]:
                with st.expander("📋 View Details"):
                    st.markdown(format_chunk_detail(chunk, show_response))
    else:
        st.info("👆 Click 'Start' to begin crawling...")

with col2:
    st.subheader("📊 Stats")
    stats = st.session_state["stats"]

    st.metric("📄 Pages", stats["pages"])
    st.metric("🔗 Links", stats["links"])
    st.metric("📝 Forms", stats["forms"])

    if stats["tech"]:
        with st.expander(f"🛠️ Tech ({len(stats['tech'])})"):
            for t in sorted(stats["tech"]):
                st.code(t)

    if stats.get("security"):
        max_security_items = 5
        security_items = stats["security"][:max_security_items]
        with st.expander(f"🔒 Security ({len(stats['security'])})", expanded=True):
            for s in security_items:
                st.warning(f"**{s['url'][:40]}...**")
                st.caption(f"Missing: {', '.join(s['missing'])}")
            if len(stats["security"]) > max_security_items:
                st.caption(f"... and {len(stats['security']) - max_security_items} more")

    st.divider()
    st.subheader("Status")

    if st.session_state.crawl_active:
        st.markdown(
            f"""
        <div class="status-box status-crawling">
            <div style="font-size: 40px;">🕷️</div>
            <div style="font-weight: bold; font-size: 20px;">CRAWLING</div>
            <div style="font-size: 14px;">Pages: {stats["pages"]}/{max_pages}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    elif st.session_state.crawl_done:
        st.markdown(
            """
        <div class="status-box status-done">
            <div style="font-size: 40px;">✅</div>
            <div style="font-weight: bold; font-size: 20px;">COMPLETE!</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    elif st.session_state.chunks and not st.session_state.crawl_active:
        st.markdown(
            """
        <div class="status-box status-stopped">
            <div style="font-size: 40px;">⏹️</div>
            <div style="font-weight: bold; font-size: 20px;">STOPPED</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
        <div class="status-box status-ready">
            <div style="font-size: 40px;">🕷️</div>
            <div style="font-weight: bold; font-size: 20px;">READY</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    if "error" in st.session_state and st.session_state.error:
        st.error(f"Error:\n{st.session_state.error}")

if st.session_state.crawl_active and auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
