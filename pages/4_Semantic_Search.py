# pages/4_Semantic_Search.py

import streamlit as st
import pandas as pd
import networkx as nx
import os
import sys
import requests
import importlib
import streamlit.components.v1 as components

# --- [PATH CONFIG] ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- [IMPORT DEPENDENCIES] ---
database = importlib.import_module("database")
page_1_explorer = importlib.import_module("pages.1_Explorer")  # for graph visualization reuse

# --- [CONFIG] ---
BACKEND_URL = "http://127.0.0.1:5000"
# Fallback CSV if Neo4j is empty
TRAINING_DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'agri_climate_relations_1000.csv')

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
        <div class="title">🔍 Semantic Search</div>
        <div class="subtitle">Find intelligent connections in your Neo4j Knowledge Graph</div>
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

# --- [SIDEBAR ACCOUNT] ---
st.sidebar.title("Account")
st.sidebar.info(f"User: **{user_info.get('logged_in_as')}**")
if st.sidebar.button("Logout 🚪"):
    st.session_state.pop("jwt_token", None)
    st.rerun()

# --- [DATA LOADING LOGIC] ---

def get_neo4j_concepts():
    """Fetches all unique node names from the active Neo4j database."""
    graph = database.get_neo4j_graph()
    if not graph:
        return []
    try:
        # Fetch up to 5000 distinct Entity names
        df = graph.run("MATCH (n:Entity) RETURN DISTINCT n.name AS name LIMIT 5000").to_data_frame()
        if not df.empty and 'name' in df.columns:
            return df['name'].dropna().astype(str).tolist()
    except Exception:
        pass
    return []

@st.cache_resource
def load_embedding_model():
    """Loads the sentence transformer model once."""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer('all-MiniLM-L6-v2')
    except ImportError:
        st.error("`sentence-transformers` not installed. Run: pip install sentence-transformers")
        return None

@st.cache_data(show_spinner=False)
def build_search_index(_model, refresh_counter):
    """
    Fetches concepts from Neo4j (preferred) or CSV (fallback) and encodes them.
    'refresh_counter' is a dummy arg used to force cache invalidation.
    """
    # 1. Try Neo4j
    concepts = get_neo4j_concepts()
    source = "Neo4j Database"
    
    # 2. Fallback to CSV if Neo4j is empty
    if not concepts:
        try:
            df = pd.read_csv(TRAINING_DATA_PATH)
            concepts = pd.concat([df['source'], df['target']]).dropna().unique().astype(str).tolist()
            source = "Sample CSV (Neo4j was empty)"
        except Exception as e:
            return [], None, f"Error: {e}"

    if not concepts:
        return [], None, "No concepts found."

    # 3. Encode
    try:
        with st.spinner(f"Indexing {len(concepts)} concepts from {source}..."):
            embeddings = _model.encode(concepts, convert_to_tensor=True)
        return concepts, embeddings, source
    except Exception as e:
        return [], None, f"Encoding Error: {e}"

# --- [MAIN APP LOGIC] ---

# 1. Load Model
model = load_embedding_model()

# 2. Manage Refresh State
if "search_refresh_counter" not in st.session_state:
    st.session_state.search_refresh_counter = 0

col_idx1, col_idx2 = st.columns([3, 1])
with col_idx2:
    if st.button("🔄 Refresh Index"):
        st.session_state.search_refresh_counter += 1
        st.cache_data.clear() # Optional: clear all data cache to be safe
        st.rerun()

# 3. Build Index
if model:
    concepts, concept_embeddings, source_label = build_search_index(model, st.session_state.search_refresh_counter)
    
    if concepts:
        with col_idx1:
            st.success(f"✅ Search Index Active: **{len(concepts)}** concepts loaded from **{source_label}**.")
    else:
        st.error("Could not load knowledge base. Please check Neo4j connection or CSV file.")
else:
    concepts, concept_embeddings = [], None

# --- [SEARCH INTERFACE] ---
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 💬 Semantic Query")

query = st.text_input("Ask something related to your data:", 
                      placeholder="e.g., How does drought affect wheat?")

if query and model and concepts and concept_embeddings is not None:
    try:
        from sentence_transformers import util

        # Perform Semantic Search
        query_embedding = model.encode(query, convert_to_tensor=True)
        cosine_scores = util.pytorch_cos_sim(query_embedding, concept_embeddings)
        
        # Get Top Results
        # We zip concepts with scores, sort descending
        results = sorted(list(zip(concepts, cosine_scores[0].tolist())), key=lambda x: x[1], reverse=True)

        st.markdown("---")
        st.markdown("### 🔎 Top Related Concepts")
        
        # Display top 5 matches
        top_node_names = []
        for text, score in results[:5]:
            st.markdown(f"- **{text}** (Similarity: {score:.2f})")
            top_node_names.append(text)

        st.markdown("---")
        st.markdown("### 🌐 Knowledge Subgraph")
        st.caption("Visualizing connections between the found concepts inside Neo4j.")

        if st.button("Generate Knowledge Subgraph", type="primary"):
            with st.spinner("Querying Neo4j for relationships..."):
                # Fetch subgraph from database.py logic
                triples = database.get_subgraph_by_names(top_node_names)

                if not triples:
                    st.warning(f"No relationships found between these nodes in Neo4j. (Nodes exist, but might be disconnected).")
                else:
                    st.info(f"Found {len(triples)} relationships.")
                    G = nx.Graph()
                    for s, r, t in triples:
                        # Ensure we label them properly for the visualizer
                        G.add_node(s, label=s, type="Entity")
                        G.add_node(t, label=t, type="Entity")
                        G.add_edge(s, t, relation=r)

                    # Use the visualizer from Explorer page
                    html = page_1_explorer.pyvis_from_nx(G, highlight=top_node_names)
                    components.html(html, height=550, scrolling=True)

    except Exception as e:
        st.error(f"Error performing semantic search: {e}")

st.markdown('</div>', unsafe_allow_html=True)