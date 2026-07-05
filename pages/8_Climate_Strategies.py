import streamlit as st, requests
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
    'static/bg_climate.png.png',
    'static/bg_climate.jpg',
    'static/bg_climate.png',
], opacity=0.60)
st.title("🌦️ Climate Smart Strategies")
API_URL = st.session_state.get('climate_api_url','http://127.0.0.1:8200')
colA, colB = st.columns([1,2])
with colA:
    api_url = st.text_input('Climate API Base URL', API_URL)
    if api_url != API_URL: st.session_state['climate_api_url'] = api_url
    loc = st.text_input('Location filter (optional)')
    crop = st.text_input('Crop filter (optional)')
    run_btn = st.button('Recommend Strategies')
    health_btn = st.button('Health')
with colB:
    st.markdown("""This module merges climate, soil, and crop data; computes a simple composite risk score; and returns top strategies matched by crop and risk context.""")

if health_btn:
    try:
        r = requests.get(f"{api_url}/health", timeout=10)
        st.info(r.json() if r.status_code==200 else r.text)
    except Exception as e:
        st.error(f"Health failed: {e}")

if run_btn:
    payload = {}
    if loc: payload['location']=loc
    if crop: payload['crop']=crop
    try:
        r = requests.post(f"{api_url}/recommend-strategy", json=payload, timeout=60)
        if r.status_code==200:
            data = r.json(); rows = data.get('results',[])
            if not rows: st.warning('No recommendations.')
            for rec in rows:
                header = f"{rec.get('location')} | {rec.get('crop')} | Risk {rec.get('risk_level')} ({rec.get('risk_score')})"
                with st.expander(header):
                    score = rec.get('risk_score',0) or 0
                    st.metric(label="Risk Score", value=f"{score:.3f}")
                    # Simple progress bar scaled to 0-1
                    st.progress(min(max(score,0),1))
                    st.write(rec)
        else:
            st.error(f"API error {r.status_code}: {r.text}")
    except Exception as e:
        st.error(f"Request failed: {e}")

st.markdown('---')
st.write('Start API: `uvicorn agrobase.module_climate_smart_farming.api:app --reload --port 8200`')
