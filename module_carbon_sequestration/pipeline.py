import os
import pandas as pd
from .carbon_engine import rule_based, scenarios

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_data")

def _read(name):
    path = os.path.join(SAMPLE_DIR, name)
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)

def run_pipeline():
    """Run a simple pipeline that merges sample inputs and computes sequestration rates.

    Returns a list of dicts with keys: location, soc, biomass, rainfall, temperature, practice, estimated_rate
    """
    soil = _read('soil_carbon.csv')
    biomass = _read('biomass.csv')
    climate = _read('climate.csv')
    management = _read('management.csv')

    if soil.empty:
        return []

    df = soil.merge(biomass, on='location', how='left')
    df = df.merge(climate, on='location', how='left')
    df = df.merge(management, on='location', how='left')

    out = []
    for _, r in df.fillna(0).iterrows():
        row = r.to_dict()
        try:
            est = rule_based(row)
            base, scens = scenarios(row, [row.get('practice','baseline')])
        except Exception:
            est = None
            base = None
            scens = []
        out.append({
            'location': row.get('location'),
            'soc': row.get('soc'),
            'biomass': row.get('biomass'),
            'rainfall': row.get('rainfall'),
            'temperature': row.get('temperature'),
            'practice': row.get('practice'),
            'estimated_rate': est,
            'baseline_rate': base,
            'scenarios': scens,
        })

    return out
