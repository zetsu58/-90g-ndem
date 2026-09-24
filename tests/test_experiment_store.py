from viral_futbol.experiment_store import ExperimentStore

def test_experiment_store_records_and_summarizes(tmp_path):
    db=str(tmp_path/"x.db")
    with ExperimentStore(db) as s:
        s.record("a","bamloop",{"mode":"exploit","motion":"pan","bucket":2})
        rows=s.summary("bamloop")
    assert rows[0]["mode"]=="exploit"
    assert rows[0]["videos"]==1
