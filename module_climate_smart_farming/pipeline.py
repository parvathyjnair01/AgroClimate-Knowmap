from .utils import load_config, save_jsonl, ensure_dir, new_id
from .data_ingest import ingest
from .processor import merge_tables
from .risk_assessment import compute_risk
from .strategy_engine import load_strategies, recommend
from .neo4j_mapper import StrategyNeo4jMapper
import csv
import os
from dotenv import load_dotenv

def run_pipeline(cfg_path=None):
    # Resolve default config path relative to this package to avoid import path issues
    if cfg_path is None:
        cfg_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    cfg = load_config(cfg_path)
    # Load environment and override Neo4j settings if present
    try:
        load_dotenv()
        env_uri = os.getenv('NEO4J_URI')
        env_user = os.getenv('NEO4J_USER')
        env_pwd = os.getenv('NEO4J_PASSWORD')
        if 'neo4j' in cfg:
            if env_uri:
                cfg['neo4j']['uri'] = env_uri
            if env_user:
                cfg['neo4j']['user'] = env_user
            if env_pwd:
                cfg['neo4j']['password'] = env_pwd
    except Exception:
        pass
    data = ingest(cfg)
    merged = merge_tables(data)
    if merged.empty: return []
    strategies_catalog = load_strategies(cfg['inputs']['strategies'])
    records = []
    for _,row in merged.iterrows():
        rd = row.to_dict(); rd['id']=new_id()
        score, level = compute_risk(rd, cfg['risk']['weights'])
        rd['risk_score']=round(score,3); rd['risk_level']=level
        recs = recommend(rd, strategies_catalog, cfg['strategy']['top_n'])
        records.append({
            'id': rd['id'],
            'location': rd.get('location'),
            'crop': rd.get('crop'),
            'risk_level': rd['risk_level'],
            'risk_score': rd['risk_score'],
            'strategies': recs
        })
    out_csv = cfg['output']['strategies_csv']; ensure_dir(out_csv)
    with open(out_csv,'w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['id','location','crop','risk_level','risk_score','strategies'])
        for r in records: w.writerow([r['id'], r['location'], r['crop'], r['risk_level'], r['risk_score'], r['strategies']])
    save_jsonl(records, cfg['output']['log_jsonl'])
    if cfg['neo4j'].get('enabled'):
        try:
            mapper = StrategyNeo4jMapper(cfg['neo4j']['uri'], cfg['neo4j']['user'], cfg['neo4j']['password'])
            mapper.map(records); mapper.close()
        except Exception as e:
            pass
    return records

if __name__=='__main__':
    rs = run_pipeline(); print('Records:', len(rs))
