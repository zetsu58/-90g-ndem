import sqlite3
from viral_futbol.retention_position import position_retention
def test_first_scene_includes_zero_ratio(tmp_path):
    db=str(tmp_path/"r.db"); c=sqlite3.connect(db)
    c.execute("CREATE TABLE scene_manifests(story_id TEXT,scene_index INT,start REAL,duration REAL)")
    c.execute("CREATE TABLE video_retention_points(story_id TEXT,video_id TEXT,elapsed_ratio REAL,audience_watch_ratio REAL)")
    c.executemany("INSERT INTO scene_manifests VALUES('s',?,?,?)",[(0,0,5),(1,5,5)])
    c.execute("INSERT INTO video_retention_points VALUES('s','v',0.0,1.0)"); c.commit(); c.close()
    assert position_retention(db,"s","v")[0]["points"]==1
