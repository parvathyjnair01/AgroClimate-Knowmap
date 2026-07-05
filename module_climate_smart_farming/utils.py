import os, json, uuid, yaml, datetime, pandas as pd

def load_config(path):
    # Resolve relative paths inside the config to this package directory
    with open(path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    base_dir = os.path.dirname(path)
    def resolve(p):
        if not isinstance(p, str):
            return p
        # If path is absolute, keep as is; else join with base_dir
        return p if os.path.isabs(p) else os.path.join(base_dir, os.path.normpath(p.replace('agrobase/module_climate_smart_farming/', '')))
    if 'inputs' in cfg:
        cfg['inputs'] = {k: resolve(v) for k,v in cfg['inputs'].items()}
    if 'output' in cfg:
        cfg['output'] = {k: resolve(v) for k,v in cfg['output'].items()}
    return cfg

def ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def save_jsonl(records, path):
    ensure_dir(path)
    with open(path,'a',encoding='utf-8') as f:
        for r in records: f.write(json.dumps(r)+'\n')

def new_id(): return str(uuid.uuid4())

def read_csv(path):
    return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()
