"""Durable queue and history. Failed discovery never advances its checkpoint."""
from contextlib import contextmanager
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
import uuid


def now():return datetime.now(timezone.utc).isoformat()

def uid():return uuid.uuid4().hex


class Store:
    def __init__(self,root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'history.sqlite3'
        with self.connection() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS videos (
              id TEXT PRIMARY KEY, douyin_id TEXT UNIQUE, sha256 TEXT UNIQUE,
              title TEXT NOT NULL, author_name TEXT, author_id TEXT, published_at INTEGER,
              original_url TEXT, source_path TEXT, transcript_path TEXT, analysis_path TEXT,
              status TEXT NOT NULL DEFAULT 'queued',error TEXT,created_at TEXT,updated_at TEXT);
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY,kind TEXT,video_id TEXT,creator_id TEXT,
              other_video_id TEXT,
              status TEXT,stage TEXT,error TEXT,attempts INTEGER DEFAULT 0,created_at TEXT,updated_at TEXT);
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_video_job ON jobs(video_id)
              WHERE kind='process' AND status IN ('queued','running');
            CREATE TABLE IF NOT EXISTS creators (
              id TEXT PRIMARY KEY,name TEXT,url TEXT UNIQUE,enabled INTEGER DEFAULT 1,
              checkpoint INTEGER,last_checked TEXT,last_error TEXT,created_at TEXT);
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_creator_job ON jobs(creator_id)
              WHERE kind='discover' AND status IN ('queued','running');
            CREATE TABLE IF NOT EXISTS discoveries (
              creator_id TEXT,video_id TEXT,published_at INTEGER,title TEXT,queued INTEGER DEFAULT 0,
              PRIMARY KEY(creator_id,video_id));
            CREATE TABLE IF NOT EXISTS comparisons (
              id TEXT PRIMARY KEY,left_id TEXT,right_id TEXT,result_json TEXT,created_at TEXT);
            ''')
            if 'other_video_id' not in {r['name'] for r in db.execute('PRAGMA table_info(jobs)')}:
                db.execute('ALTER TABLE jobs ADD COLUMN other_video_id TEXT')

    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=30)
        db.row_factory=sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback();raise
        finally:db.close()

    def all(self,table):
        if table not in {'videos','jobs','creators','comparisons'}:raise ValueError('Invalid table')
        with self.connection() as db:
            rows=db.execute(f'SELECT * FROM {table} ORDER BY created_at DESC').fetchall()
        return [dict(r) for r in rows]

    def video(self,id):
        with self.connection() as db:r=db.execute('SELECT * FROM videos WHERE id=?',(id,)).fetchone()
        return dict(r) if r else None

    def add_video(self,**fields):
        stamp=now()
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            for key in ['sha256','douyin_id']:
                if fields.get(key):
                    row=db.execute(f'SELECT id FROM videos WHERE {key}=?',(fields[key],)).fetchone()
                    if row:return row['id'],False
            vid=uid()
            keys=['douyin_id','sha256','title','author_name','author_id','published_at','original_url','source_path','transcript_path','analysis_path']
            db.execute(f'INSERT INTO videos(id,{",".join(keys)},status,created_at,updated_at) VALUES ({",".join("?" for _ in range(len(keys)+4))})',
                       [vid]+[fields.get(k) for k in keys]+['queued',stamp,stamp])
            return vid,True

    def update_video(self,id,**fields):
        allowed={'sha256','source_path','transcript_path','analysis_path','status','error','title','author_name','author_id','published_at'}
        if not set(fields)<=allowed:raise ValueError('Unknown video fields')
        fields['updated_at']=now()
        with self.connection() as db:
            db.execute('UPDATE videos SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',list(fields.values())+[id])

    def enqueue(self,kind,video_id=None,creator_id=None,other_video_id=None):
        if kind not in {'process','discover','compare'}:raise ValueError('Invalid job')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if kind=='compare':
                existing=db.execute("SELECT id FROM jobs WHERE kind='compare' AND ((video_id=? AND other_video_id=?) OR (video_id=? AND other_video_id=?)) AND status IN ('queued','running')",(video_id,other_video_id,other_video_id,video_id)).fetchone()
            else:
                existing=db.execute("SELECT id FROM jobs WHERE kind=? AND video_id IS ? AND creator_id IS ? AND status IN ('queued','running')",(kind,video_id,creator_id)).fetchone()
            if existing:return existing['id']
            job=uid();stamp=now()
            db.execute('INSERT INTO jobs(id,kind,video_id,creator_id,other_video_id,status,stage,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(job,kind,video_id,creator_id,other_video_id,'queued','等待处理',stamp,stamp))
            return job

    def claim_job(self):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:return None
            db.execute("UPDATE jobs SET status='running',attempts=attempts+1,updated_at=? WHERE id=?",(now(),row['id']))
            return dict(row)

    def job_status(self,id,status,stage,error=None):
        with self.connection() as db:
            db.execute('UPDATE jobs SET status=?,stage=?,error=?,updated_at=? WHERE id=?',(status,stage,error,now(),id))

    def recover(self):
        with self.connection() as db:
            db.execute("UPDATE jobs SET status='queued',stage='上次中断，等待继续',updated_at=? WHERE status='running'",(now(),))

    def add_creator(self,url,name):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT id FROM creators WHERE url=?',(url,)).fetchone()
            if row:return row['id']
            id=uid();db.execute('INSERT INTO creators(id,name,url,created_at) VALUES(?,?,?,?)',(id,name,url,now()))
            return id

    def creator(self,id):
        with self.connection() as db:r=db.execute('SELECT * FROM creators WHERE id=?',(id,)).fetchone()
        return dict(r) if r else None

    def save_discovery(self,id,result):
        # Safe advancement requires the collector to have reached the requested boundary.
        with self.connection() as db:
            for row in result['videos']:
                db.execute('INSERT OR IGNORE INTO discoveries(creator_id,video_id,published_at,title) VALUES(?,?,?,?)',
                           (id,row['video_id'],row.get('published_at'),row.get('title','')))
            if result['complete']:
                db.execute('UPDATE creators SET checkpoint=?,last_checked=?,last_error=NULL WHERE id=?',
                           (result['checked_at_epoch'],now(),id))
            else:
                db.execute('UPDATE creators SET last_checked=?,last_error=? WHERE id=?',
                           (now(),'已保存本次发现，但分页未覆盖到上次检查位置，保留旧检查点',id))

    def pending_discoveries(self,id):
        with self.connection() as db:return [dict(r) for r in db.execute('SELECT * FROM discoveries WHERE creator_id=? AND queued=0',(id,))]

    def mark_discovery_queued(self,creator_id,video_id):
        with self.connection() as db:db.execute('UPDATE discoveries SET queued=1 WHERE creator_id=? AND video_id=?',(creator_id,video_id))

    def creator_error(self,id,error):
        with self.connection() as db:db.execute('UPDATE creators SET last_error=?,last_checked=? WHERE id=?',(error,now(),id))

    def save_comparison(self,left,right,result):
        # Keep the cited version: re-analysis can change claim numbering later.
        result=dict(result);result['sources']={}
        for side,id in [('left',left),('right',right)]:
            video=self.video(id)
            path=video.get('analysis_path') if video else None
            analysis=json.loads(Path(path).read_text()) if path and Path(path).is_file() else {}
            claims=analysis.get('claims',[])
            result['sources'][side]={'title':video['title'] if video else '原视频不可用',
                'claims':[claims[i-1] for i in result.get(side+'_claim_ids',[]) if 0<i<=len(claims)],
                'source_sha256':analysis.get('source_sha256'),'provenance':analysis.get('provenance')}
        stamp=now()
        with self.connection() as db:
            db.execute('INSERT INTO comparisons(id,left_id,right_id,result_json,created_at) VALUES(?,?,?,?,?)',
                       (uid(),left,right,json.dumps(result,ensure_ascii=False),stamp))
            db.execute('UPDATE videos SET updated_at=? WHERE id IN (?,?)',(stamp,left,right))
