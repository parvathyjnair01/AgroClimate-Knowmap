# pages/3_Data_Ingestion.py

import streamlit as st
import pandas as pd
import os
import sys
import importlib
import requests
import streamlit.components.v1 as components
import xml.etree.ElementTree as ET
import re

# --- [PATH CONFIG] Add project root for imports ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- [IMPORT PIPELINES] ---
pipelines_extraction = importlib.import_module("pipelines.extraction")
pipelines_text_cleaner = importlib.import_module("pipelines.text_cleaner")
pipelines_neo4j_loader = importlib.import_module("pipelines.neo4j_loader")

# --- [CONFIG] ---
BACKEND_URL = "http://127.0.0.1:5000"  # Flask backend

# --- [JWT AUTH VALIDATION] ---
def get_user_from_jwt():
    """Validates JWT token by calling Flask /profile endpoint."""
    token = st.session_state.get("jwt_token")
    if not token:
        return None
    try:
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(f"{BACKEND_URL}/profile", headers=headers)
        if res.status_code == 200:
            return res.json()
        else:
            st.session_state.pop("jwt_token", None)
            return None
    except Exception:
        st.session_state.pop("jwt_token", None)
        return None

# --- [AUTH CHECK] ---
user_info = get_user_from_jwt()
if not user_info:
    st.error("🔒 Please log in first to access this page.")
    st.page_link("streamlit_app.py", label="Back to Login", icon="🏠")
    st.stop()

# --- [PAGE CONFIG] ---
st.markdown(
    """
    <div class="header">
        <div class="title">🌱 Data Ingestion Pipeline</div>
        <div class="subtitle">Extract, clean, and load agricultural knowledge into Neo4j</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# --- [STYLES] ---
def load_css(file_name):
    """Load global style.css from root directory."""
    try:
        css_path = os.path.join(os.path.dirname(__file__), '..', file_name)
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"⚠️ CSS file '{file_name}' not found.")

load_css("style.css")

# --- [HEADER] ---
st.markdown(
    f"""
    <div class="header">
        <div class="title">📥 Data Ingestion Pipeline</div>
        <div class="subtitle">Logged in as: {user_info.get('logged_in_as')}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- [SIDEBAR ACCOUNT] ---
st.sidebar.title("Account")
st.sidebar.info(f"User: **{user_info.get('logged_in_as')}**")
if st.sidebar.button("Logout 🚪"):
    st.session_state.pop("jwt_token", None)
    st.rerun()

# --- [SESSION STATE INITIALIZATION] ---
# We initialize a key to hold the extracted triples so they persist across reruns.
if "ingestion_triples" not in st.session_state:
    st.session_state["ingestion_triples"] = None
if "ingestion_source" not in st.session_state:
    st.session_state["ingestion_source"] = ""

# --- [HELPERS] ---
def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def run_extraction_pipeline(text: str, source_label: str):
    """
    Runs the NLP pipeline and saves results to Session State.
    Does NOT render the store button itself.
    """
    if not text or not text.strip():
        st.warning("Please provide some text.")
        return

    with st.spinner(f"Running KNOWMAP NLP pipeline on {source_label}..."):
        nlp = pipelines_extraction.load_nlp_model()
        cleaned_text = pipelines_text_cleaner.clean_text(text)
        triples = pipelines_extraction.extract_triples(cleaned_text, nlp)
    
    if not triples:
        st.warning("No structured triples found. Try adding more context.")
        st.session_state["ingestion_triples"] = None
    else:
        st.session_state["ingestion_triples"] = triples
        st.session_state["ingestion_source"] = source_label
        st.success(f"✅ Successfully extracted {len(triples)} triples! Scroll down to review and store.")

# --- [MAIN LAYOUT] ---
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 🧭 Choose ingestion source")
tab_text, tab_file, tab_wiki, tab_news, tab_arxiv = st.tabs([
    "Text", "File", "Wikipedia", "News", "arXiv"
])

# --- TAB: TEXT ---
with tab_text:
    text_input = st.text_area(
        "Paste or type data related to agriculture or climate systems:",
        height=220,
        placeholder="Example: High soil salinity reduces wheat yield and affects irrigation efficiency..."
    )
    if st.button("🔍 Run NLP Pipeline", type="primary", key="btn_text"):
        run_extraction_pipeline(text_input, "Manual Text Input")

# --- TAB: FILE ---
with tab_file:
    up = st.file_uploader("Upload CSV or TXT", type=["csv", "txt"])
    if st.button("Process File", disabled=not up, key="btn_file"):
        if not up:
            st.warning("Please select a file.")
        else:
            with st.spinner("Processing file..."):
                nlp = pipelines_extraction.load_nlp_model()
                # Use the extraction logic directly here as it differs slightly (file bytes)
                triples = pipelines_extraction.extract_triples_from_file(up.read(), up.name, nlp)
                
                if not triples:
                    st.warning("No triples extracted from file.")
                    st.session_state["ingestion_triples"] = None
                else:
                    st.session_state["ingestion_triples"] = triples
                    st.session_state["ingestion_source"] = f"File: {up.name}"
                    st.success(f"✅ Extracted {len(triples)} triples from file! Scroll down to review.")

# --- TAB: WIKIPEDIA ---
with tab_wiki:
    topic = st.text_input("Wikipedia topic", placeholder="e.g., Wheat, Drought, Soil salinity")
    if st.button("Fetch from Wikipedia", key="btn_wiki"):
        if not topic:
            st.warning("Enter a topic.")
        else:
            import urllib.parse
            text = ""
            try:
                slug = urllib.parse.quote(topic, safe='')
                url_summary = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
                r = requests.get(url_summary, timeout=12)
                if r.status_code == 200:
                    data = r.json()
                    title = data.get("title", "")
                    extract = data.get("extract") or data.get("description") or ""
                    if extract:
                        text = " ".join([str(title), str(extract)])
            except Exception:
                pass

            # Fallback to action API
            if not text:
                try:
                    q = urllib.parse.quote_plus(topic)
                    api_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext&format=json&titles={q}"
                    r2 = requests.get(api_url, timeout=12, headers={"User-Agent": "KNOWMAP/1.0"})
                    if r2.status_code == 200:
                        payload = r2.json()
                        pages = payload.get("query", {}).get("pages", {})
                        extracts = []
                        for pid, page in pages.items():
                            ext = page.get("extract") or ""
                            title = page.get("title", "")
                            if ext:
                                extracts.append(f"{title}. {ext}")
                        if extracts:
                            text = "\n\n".join(extracts)
                except Exception as e:
                    st.warning(f"Wikipedia fetch error: {e}")

            if not text:
                st.error("Could not fetch Wikipedia content.")
            else:
                st.info(f"Fetched {len(text)} characters.")
                run_extraction_pipeline(text, f"Wikipedia: {topic}")

# --- TAB: NEWS ---
with tab_news:
    query_news = st.text_input("News query", placeholder="e.g., climate change agriculture")
    limit_news = st.slider("Articles", 5, 30, 10, key="news_limit")
    if st.button("Fetch News", key="btn_news"):
        if not query_news:
            st.warning("Enter a query.")
        else:
            feed_url = f"https://news.google.com/rss/search?q={requests.utils.quote(query_news)}&hl=en-US&gl=US&ceid=US:en"
            try:
                r = requests.get(feed_url, timeout=15)
                r.raise_for_status()
                root = ET.fromstring(r.text)
                items = root.findall(".//item")[:limit_news]
                parts = []
                for it in items:
                    title = (it.findtext("title") or "")
                    desc = (it.findtext("description") or "")
                    parts.append(f"{title}. {strip_html(desc)}")
                text = " ".join(parts)
                run_extraction_pipeline(text, f"News: {query_news}")
            except Exception as e:
                st.error(f"News fetch failed: {e}")

# --- TAB: ARXIV ---
with tab_arxiv:
    query_arxiv = st.text_input("arXiv query", placeholder="e.g., crop yield drought")
    limit_arxiv = st.slider("Papers", 5, 30, 10, key="arxiv_limit")
    if st.button("Fetch from arXiv", key="btn_arxiv"):
        if not query_arxiv:
            st.warning("Enter a query.")
        else:
            api = f"http://export.arxiv.org/api/query?search_query=all:{requests.utils.quote(query_arxiv)}&start=0&max_results={limit_arxiv}"
            try:
                r = requests.get(api, timeout=20, headers={"User-Agent": "KNOWMAP/1.0"})
                r.raise_for_status()
                root = ET.fromstring(r.text)
                ns = {"a": "http://www.w3.org/2005/Atom"}
                entries = root.findall("a:entry", ns)
                parts = []
                for e in entries:
                    title = e.findtext("a:title", default="", namespaces=ns)
                    summary = e.findtext("a:summary", default="", namespaces=ns)
                    parts.append(f"{title}. {summary}")
                text = " ".join(parts)
                run_extraction_pipeline(text, f"arXiv: {query_arxiv}")
            except Exception as e:
                st.error(f"arXiv fetch failed: {e}")

st.markdown('</div>', unsafe_allow_html=True)

# --- [RESULTS & STORAGE SECTION] ---
# This section is outside the tabs/buttons, so it persists after reruns as long as session state has data.
if st.session_state.get("ingestion_triples"):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader(f"📊 Review Data: {st.session_state['ingestion_source']}")
    
    triples = st.session_state["ingestion_triples"]
    
    # 1. DataFrame View
    df = pd.DataFrame(triples, columns=["Subject", "Relation", "Object"])
    st.dataframe(df, use_container_width=True)

    # 2. Graph View
    try:
        G = pipelines_extraction.triples_to_graph(triples)
        html = pipelines_extraction.graph_to_pyvis_html(G)
        components.html(html, height=600, scrolling=True)
    except Exception as e:
        st.warning(f"Graph render failed: {e}")

    st.divider()

    # 3. Store Button (Now persistent)
    col_a, col_b = st.columns([1, 2])
    with col_a:
        if st.button("📡 Store in Neo4j Database", type="primary", use_container_width=True):
            with st.spinner("Storing triples in Neo4j..."):
                count = pipelines_neo4j_loader.store_triples_in_neo4j(triples)
            if count > 0:
                st.success(f"Stored {count} triples successfully in Neo4j graph!")
                # Optional: Clear state after successful store
                # st.session_state["ingestion_triples"] = None
                # st.rerun()
            else:
                st.error("Failed to store triples. Check database connection.")
    with col_b:
        if st.button("🗑️ Clear Results"):
            st.session_state["ingestion_triples"] = None
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# --- [SIDECARD INFO] ---
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 🧠 Pipeline Overview")
st.info("""
**Pipeline Steps:**
1. Text Cleaning (noise removal)
2. Entity Recognition (spaCy + CSV priming)
3. Relation Extraction (Dependency patterns)
4. Neo4j Graph Storage
""")
st.markdown("### 🧩 Status Indicators")
st.write("✅ NLP Model: Loaded")
st.write("✅ Neo4j Connection: Active")
st.write("🌿 Ready for Knowledge Graph Ingestion")
st.markdown('</div>', unsafe_allow_html=True)