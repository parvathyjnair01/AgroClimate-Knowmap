import streamlit as st
import os
import sqlite3
import pandas as pd
import importlib
import requests

# --- Local imports ---
database = importlib.import_module("database")

BACKEND_URL = "http://127.0.0.1:5000"


def load_css(file_name="style.css"):
    try:
        base_dir = os.path.dirname(__file__)
        candidates = [
            os.path.join(base_dir, file_name),
            os.path.join(base_dir, "..", file_name),
        ]
        for path in candidates:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
                return
        st.warning(f"CSS file '{file_name}' not found near {base_dir}")
    except Exception as e:
        st.warning(f"CSS Load Error: {e}")


def get_user_from_jwt():
    token = st.session_state.get("jwt_token")
    if not token:
        return None
    try:
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(f"{BACKEND_URL}/profile", headers=headers, timeout=8)
        if res.status_code == 200:
            return res.json()
        st.session_state.pop("jwt_token", None)
        return None
    except Exception:
        st.session_state.pop("jwt_token", None)
        return None


def find_sqlite_db_candidates():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    candidates = [
        os.path.join(base, 'auth_backend', 'flask_users.db'),
        os.path.join(base, 'flask_users.db'),
        os.path.join(base, 'auth_backend', 'flask_feedback.db'),
        os.path.join(base, 'flask_feedback.db'),
    ]
    return [p for p in candidates if os.path.exists(p)]


def list_users_from_db(db_path):
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query('SELECT id, email FROM users ORDER BY id DESC LIMIT 100', conn)
        conn.close()
        return df
    except Exception:
        return None


st.markdown("# ⚙️ Admin Dashboard")
load_css()

user_info = get_user_from_jwt()
if not user_info:
    st.error("🔒 Admin access requires signing in.")
    st.stop()

st.write(f"Signed in as: **{user_info.get('logged_in_as')}**")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Neo4j Status & Controls")
    graph = database.get_neo4j_graph()
    if not graph:
        st.warning("Neo4j not connected. Check .env and backend.")
    else:
        try:
            nodes = graph.run("MATCH (n) RETURN count(n) AS c").evaluate()
            rels = graph.run("MATCH ()-[r]-() RETURN count(r) AS c").evaluate()
            st.metric("Nodes", nodes)
            st.metric("Relationships", rels)
            # Streamlit has no st.confirm; use checkbox-gated delete
            st.warning("This will DELETE ALL nodes and relationships.")
            confirm_delete = st.checkbox(
                "I understand. Proceed with deletion.", key="confirm_delete_main"
            )
            col_left, col_right = st.columns([1, 1])
            with col_left:
                delete_clicked = st.button(
                    "Clear Neo4j Database (DELETE ALL)",
                    type="primary",
                    disabled=not confirm_delete,
                    key="btn_delete_all",
                )
            with col_right:
                confirm_clicked = st.button(
                    "Confirm Delete",
                    type="secondary",
                    disabled=not confirm_delete,
                    key="btn_confirm_delete",
                )
            if (delete_clicked or confirm_clicked) and confirm_delete:
                with st.spinner("Clearing database..."):
                    ok = database.clear_database()
                    if ok:
                        st.success("Neo4j cleared.")
                    else:
                        st.error("Failed to clear Neo4j")
        except Exception as e:
            st.error(f"Error querying Neo4j: {e}")

with col2:
    st.subheader("User Accounts")
    dbs = find_sqlite_db_candidates()
    if not dbs:
        st.info("No local user DB found (expected at auth_backend/flask_users.db)")
    else:
        for db in dbs:
            st.markdown(f"**DB:** {db}")
            df = list_users_from_db(db)
            if df is None or df.empty:
                st.write("No users found.")
            else:
                st.dataframe(df, use_container_width=True)

st.markdown("---")
st.subheader("Feedback & Logs")
feedback_paths = [
    os.path.join(os.path.dirname(__file__), '..', 'auth_backend', 'feedback.db'),
    os.path.join(os.path.dirname(__file__), '..', 'feedback_local.csv'),
]
found = False
for p in feedback_paths:
    if os.path.exists(p):
        found = True
        st.markdown(f"**Feedback source:** {p}")
        try:
            if p.endswith('.db'):
                conn = sqlite3.connect(p)
                df_fb = pd.read_sql_query('SELECT id, user_email, feedback_type, feedback_text, created_at FROM feedback ORDER BY id DESC LIMIT 200', conn)
                conn.close()
            else:
                df_fb = pd.read_csv(p)
            st.dataframe(df_fb.head(200), use_container_width=True)
        except Exception as e:
            st.warning(f"Failed reading feedback: {e}")
if not found:
    st.info("No feedback storage found. Users can submit feedback from the Feedback page; fallback will save locally.")

st.markdown("---")
st.write("If you need more admin features (user delete, role management, feedback export), I can add them.")
