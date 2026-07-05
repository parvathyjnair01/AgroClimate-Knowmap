import streamlit as st
import requests
import os, base64


def _set_page_background(candidates, opacity: float = 0.18) -> None:
    try:
        chosen = None
        base_dir = os.path.dirname(__file__)
        for c in candidates:
            paths = [
                os.path.normpath(os.path.join(os.getcwd(), c)),
                os.path.normpath(os.path.join(base_dir, '..', c)),
            ]
            for p in paths:
                if os.path.exists(p):
                    chosen = p
                    break
            if chosen:
                break
        if not chosen:
            return
        with open(chosen, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        overlay = max(0.0, min(1.0, opacity))
        st.markdown(
            f"""
            <style>
            [data-testid=\"stAppViewContainer\"] {{
                background-image: linear-gradient(rgba(255,255,255,{overlay}), rgba(255,255,255,{overlay})), url('data:image;base64,{b64}');
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
            }}
            [data-testid=\"stHeader\"], [data-testid=\"stToolbar\"] {{ background: transparent; }}
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass

_set_page_background([
    'static/bg_carbon.png.jpg',
    'static/bg_carbon.jpg',
    'static/bg_carbon.png',
], opacity=0.60)
st.title("🌳 Carbon Sequestration")
st.caption("Run the carbon pipeline API and explore practice scenarios.")

API_URL = st.session_state.get('carbon_api_url', 'http://127.0.0.1:8100')

with st.sidebar:
    st.subheader("Carbon Module Settings")
    api_url = st.text_input("API Base URL", API_URL)
    if api_url != API_URL:
        st.session_state['carbon_api_url'] = api_url
    location_filter = st.text_input("Filter by Location (optional)")
    run_btn = st.button("Run Pipeline")
    health_btn = st.button("Health Check")

if health_btn:
    try:
        h = requests.get(f"{api_url}/health", timeout=10)
        st.info(h.json() if h.status_code == 200 else h.text)
    except Exception as e:
        st.error(f"Health request failed: {e}")

if run_btn:
    payload = {}
    if location_filter:
        payload['location'] = location_filter
    try:
        r = requests.post(f"{api_url}/carbon-sequestration", json=payload, timeout=60)
        if r.status_code == 200:
            data = r.json()
            results = data.get('results', [])
            if not results:
                st.warning("No results returned. Ensure sample_data CSVs present.")
            for rec in results:
                with st.expander(f"Location: {rec.get('location')} | Baseline: {rec.get('baseline_rate'):.2f}"):
                    st.write({k: v for k, v in rec.items() if k != 'scenarios'})
                    scenarios = rec.get('scenarios', [])
                    if scenarios:
                        st.markdown("**Scenarios**")
                        for s in scenarios:
                            st.write(f"• {s['practice']}: {s['estimated_rate']:.2f} (factor {s['factor']})")
        else:
            st.error(f"API error {r.status_code}: {r.text}")
    except Exception as e:
        st.error(f"Pipeline request failed: {e}")

st.markdown("---")
st.write("Tip: Start the API with: `uvicorn agrobase.module_carbon_sequestration.api:app --reload --port 8100`")
