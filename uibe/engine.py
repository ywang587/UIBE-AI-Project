"""Sequential, restartable local media pipeline and in-app monitoring."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import threading
import time
from filelock import FileLock,Timeout as LockTimeout
from .store import Store,now
from .analysis import PROMPT_VERSION

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'scripts'))
from transcribe import sha256
from course_urls import extract
from check_download import read_jsonl


class Engine:
    def __init__(self,root):
        self.store=Store(root);self.root=self.store.root
        self.config_path=self.root/'settings.json'
        self.stop_event=threading.Event();self.thread=None;self.child=None
        self.run_lock=FileLock(self.root/'application.lock')
        self.settings={'python':sys.executable,'asr_python':sys.executable,
                       'model':'mlx-community/Qwen3-4B-Instruct-2507-4bit','asr_model':'medium',
                       'crawler_dir':str(REPO.parent/'MediaCrawler'),
                       'crawler_python':str(REPO.parent/'MediaCrawler/.venv/bin/python'),
                       'node_dir':'','monitor_interval_minutes':60,'lookback_days':14,
                       'monitor_enabled':False,'auto_process_discoveries':False}
        if self.config_path.exists():self.settings.update(json.loads(self.config_path.read_text()))

    def save_settings(self,updates):
        allowed={'model','asr_model','crawler_dir','crawler_python','asr_python','python','node_dir',
                 'monitor_interval_minutes','monitor_enabled','auto_process_discoveries','lookback_days'}
        if not set(updates)<=allowed:raise ValueError('未知设置')
        merged={**self.settings,**updates}
        if not 5<=int(merged['monitor_interval_minutes'])<=1440:raise ValueError('检查间隔应在5至1440分钟之间')
        if not 1<=int(merged['lookback_days'])<=90:raise ValueError('回查范围应在1至90天之间')
        self.settings=merged
        temp=self.config_path.with_suffix('.tmp');temp.write_text(json.dumps(merged,ensure_ascii=False,indent=2));os.replace(temp,self.config_path)

    def import_file(self,path,title=None):
        path=Path(path).expanduser().resolve(strict=True)
        if path.suffix.lower() not in {'.mp4','.mov','.mkv','.webm','.m4a','.mp3','.wav'}:raise ValueError('不支持的媒体类型')
        digest=sha256(path)
        vid,created=self.store.add_video(sha256=digest,title=title or path.stem,source_path=str(path))
        if created:self.store.enqueue('process',video_id=vid)
        else:
            previous=self.store.video(vid)
            if not previous['source_path'] or not Path(previous['source_path']).is_file():
                self.store.update_video(vid,source_path=str(path),error=None)
                if previous['status'] not in {'ready','irrelevant'}:
                    self.store.update_video(vid,status='queued')
                    self.store.enqueue('process',video_id=vid)
        return vid,created

    def import_links(self,text):
        results=[]
        for url in extract(text):
            dyid=url.rsplit('/',1)[-1]
            vid,created=self.store.add_video(douyin_id=dyid,title='等待获取视频信息',original_url=url)
            if created:self.store.enqueue('process',video_id=vid)
            results.append({'id':vid,'created':created})
        if not results:raise ValueError('未找到有效抖音视频链接')
        return results

    def start(self):
        try:self.run_lock.acquire(timeout=0)
        except LockTimeout as error:raise RuntimeError('此资料目录已有观潮在运行，请使用已打开的窗口') from error
        self.store.recover();self.stop_event.clear()
        if self.settings['monitor_enabled']:
            for creator in self.store.all('creators'):
                if creator['enabled']:self.store.enqueue('discover',creator_id=creator['id'])
        self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.child and self.child.poll() is None:self.terminate_child()
        if self.thread:self.thread.join(timeout=10)
        self.run_lock.release()

    def terminate_child(self,force=False):
        if not self.child or self.child.poll() is not None:return
        try:
            if os.name=='posix':os.killpg(self.child.pid,signal.SIGKILL if force else signal.SIGTERM)
            elif force:self.child.kill()
            else:self.child.terminate()
        except ProcessLookupError:pass

    def command(self,args,log,timeout=3600):
        env=os.environ.copy()
        if 'uibe.model_worker' in args:
            env['HF_HOME']=str(REPO/'local_data/model-cache')
        # ASR uses the existing normal Hugging Face cache, independently of MLX.
        env['PYTHONUNBUFFERED']='1'
        env['PYTHONPYCACHEPREFIX']=str(self.root/'pycache')
        if self.settings['node_dir']:env['PATH']=self.settings['node_dir']+os.pathsep+env.get('PATH','')
        log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('w') as out:
            self.child=subprocess.Popen([str(x) for x in args],cwd=REPO,env=env,stdout=out,stderr=out,start_new_session=(os.name=='posix'))
            started=time.monotonic()
            while self.child.poll() is None:
                if self.stop_event.wait(.25):
                    self.terminate_child()
                    try:self.child.wait(timeout=5)
                    except subprocess.TimeoutExpired:self.terminate_child(force=True);self.child.wait()
                    raise InterruptedError('程序关闭，下次启动继续')
                if time.monotonic()-started>timeout:
                    self.terminate_child(force=True);self.child.wait();raise TimeoutError('处理超时，可查看记录并重试')
            if self.child.returncode:
                text=log.read_text(errors='replace')
                if 'UIBE_LOGIN_REQUIRED' in text:raise RuntimeError('抖音登录已失效，请从课程下载入口完成登录后重试')
                raise RuntimeError(f'步骤执行失败（退出码 {self.child.returncode}），详见 {log.name}')

    def stage(self,job,name):self.store.job_status(job['id'],'running',name)

    def process(self,job):
        vid=job['video_id'];video=self.store.video(vid);out=self.root/'videos'/vid/'runs'/job['id'];out.mkdir(parents=True,exist_ok=True)
        self.store.update_video(vid,status='processing',error=None)
        source=Path(video['source_path']) if video['source_path'] else None
        if not source or not source.exists():
            if not video['douyin_id']:raise FileNotFoundError('原视频已移动或丢失，请重新导入')
            self.stage(job,'下载视频')
            downloaded=self.root/'downloads'
            self.command([self.settings['crawler_python'],REPO/'scripts/probe_download.py',self.settings['crawler_dir'],video['douyin_id'],'--output',downloaded],out/'download.log',180)
            source=downloaded/'dy/media'/video['douyin_id']/'video.mp4'
            if not source.exists():raise RuntimeError('下载程序结束，但没有产生 MP4')
            metadata=[r for p in downloaded.glob('douyin/jsonl/*.jsonl') for r in read_jsonl(p) if r.get('aweme_id')==video['douyin_id']]
            if not metadata:raise RuntimeError('视频已下载，但缺少对应详情')
            r=metadata[-1]
            name=r.get('nickname') or video.get('author_name')
            if name and '*' in name and video.get('author_name'):
                name=video['author_name']
            self.store.update_video(vid,source_path=str(source),title=r.get('desc','视频')[:180],
                author_name=name,author_id=video.get('author_id') or r.get('sec_uid') or r.get('user_id'),
                author_hash=r.get('creator_hash') or video.get('author_hash'),published_at=r.get('create_time'))
        digest=sha256(source)
        duplicate=next((r for r in self.store.all('videos') if r['sha256']==digest and r['id']!=vid),None)
        if duplicate:
            self.store.update_video(vid,status='duplicate',error='与已有视频重复：'+duplicate['id'],source_path=str(source),transcript_path=duplicate['transcript_path'],analysis_path=duplicate['analysis_path'])
            return
        self.store.update_video(vid,sha256=digest)
        video=self.store.video(vid)
        transcript=Path(video['transcript_path']) if video['transcript_path'] else None
        if transcript and transcript.is_file():
            saved=json.loads(transcript.read_text())
            if saved.get('settings',{}).get('model')!=self.settings['asr_model']:
                transcript=None
        if not transcript or not transcript.is_file():
            self.stage(job,'转录音轨')
            # Restore ASR cache lookup for the existing medium model.
            args=[self.settings['asr_python'],REPO/'scripts/transcribe.py',source,'--output',out/'transcripts','--model',self.settings['asr_model']]
            self.command(args,out/'transcribe.log')
            candidates=[]
            for candidate in (out/'transcripts').glob('*/transcript.json'):
                saved=json.loads(candidate.read_text())
                if saved.get('source',{}).get('sha256')==digest and saved.get('settings',{}).get('model')==self.settings['asr_model']:
                    candidates.append(candidate)
            if not candidates:raise RuntimeError('转录没有产生完整结果')
            transcript=max(candidates,key=lambda p:p.stat().st_mtime)
            self.store.update_video(vid,transcript_path=str(transcript))
        t=json.loads(transcript.read_text())
        if t['source']['sha256']!=digest:raise ValueError('转录与原视频内容不一致，拒绝继续分析')
        self.stage(job,'提取观点与证据')
        metadata=out/'metadata.json';metadata.write_text(json.dumps(self.store.video(vid),ensure_ascii=False))
        analysis=out/'analysis.json'
        self.command([self.settings['python'],'-m','uibe.model_worker','--transcript',transcript,'--metadata',metadata,'--model',self.settings['model'],'--output',analysis],out/'analysis.log',1800)
        result=json.loads(analysis.read_text())
        if result['source_sha256']!=digest:raise ValueError('分析来源校验失败')
        from .background import supplement
        result=supplement(result,self.store.video(vid)['title'])
        temp=analysis.with_suffix('.background.tmp')
        temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        os.replace(temp,analysis)
        self.store.update_video(vid,analysis_path=str(analysis),status='ready' if result['relevant'] else 'irrelevant',error=None)

    def with_analysis(self,v):
        v=dict(v)
        if v.get('analysis_path') and Path(v['analysis_path']).is_file():
            v['analysis']=json.loads(Path(v['analysis_path']).read_text())
        return v

    def compare_pair(self,job,current,other):
        self.stage(job,'对照视频：'+other['title'][:30])
        folder=self.root/'comparisons'/job['id'];folder.mkdir(parents=True,exist_ok=True)
        source=folder/(other['id']+'-input.json');target=folder/(other['id']+'-result.json')
        source.write_text(json.dumps({'left':current,'right':other},ensure_ascii=False))
        self.command([self.settings['python'],'-m','uibe.model_worker','--compare',source,'--model',self.settings['model'],'--output',target],folder/(other['id']+'.log'),900)
        self.store.save_comparison(current['id'],other['id'],json.loads(target.read_text()))

    def compare_history(self,job):
        from .comparison import candidates
        current=self.store.video(job['video_id'])
        if current['status']!='ready':return
        current=self.with_analysis(current)
        others=[self.with_analysis(v) for v in self.store.all('videos') if v['status']=='ready']
        for other in candidates(current,others):
            try:
                self.compare_pair(job,current,other)
            except InterruptedError:raise
            except Exception as error:
                self.store.save_comparison(current['id'],other['id'],{'relation':'比较失败','reason':str(error),'left_claim_ids':[],'right_claim_ids':[]})

    def discover(self,job):
        creator=self.store.creator(job['creator_id'])
        if not creator:raise ValueError('博主已不存在')
        self.stage(job,'检查博主更新')
        since=creator['checkpoint'] or int(time.time())-int(self.settings['lookback_days'])*86400
        out=self.root/'creators'/creator['id'];out.mkdir(parents=True,exist_ok=True)
        response=out/'discovery.json'
        if response.exists():response.unlink() # A failed run must never reuse a stale successful response.
        self.command([self.settings['crawler_python'],REPO/'scripts/discover_creator.py',self.settings['crawler_dir'],creator['url'],'--since',str(since),'--max-pages','3','--output',response],out/'discovery.log',180)
        result=json.loads(response.read_text());self.store.save_discovery(creator['id'],result)
        if self.settings['auto_process_discoveries']:
            for row in self.store.pending_discoveries(creator['id']):
                vid,created=self.store.add_video(douyin_id=row['video_id'],title=row['title'][:180] or '新视频',author_name=creator['name'],author_id=creator['url'].rsplit('/',1)[-1],published_at=row['published_at'],original_url='https://www.douyin.com/video/'+row['video_id'])
                if created:self.store.enqueue('process',video_id=vid)
                self.store.mark_discovery_queued(creator['id'],row['video_id'])

    def schedule(self):
        if not self.settings['monitor_enabled']:return
        for c in self.store.all('creators'):
            if not c['enabled']:continue
            last=datetime.fromisoformat(c['last_checked']).timestamp() if c['last_checked'] else 0
            if time.time()-last>=int(self.settings['monitor_interval_minutes'])*60:
                self.store.enqueue('discover',creator_id=c['id'])

    def loop(self):
        last_schedule=0
        while not self.stop_event.is_set():
            if time.monotonic()-last_schedule>60:
                self.schedule();last_schedule=time.monotonic()
            job=self.store.claim_job()
            if not job:self.stop_event.wait(1);continue
            try:
                if job['kind']=='process':
                    self.process(job)
                    self.compare_history(job)
                elif job['kind']=='compare':
                    left=self.with_analysis(self.store.video(job['video_id']))
                    right=self.with_analysis(self.store.video(job['other_video_id']))
                    if left['status']!='ready' or right['status']!='ready':raise ValueError('请等待两条视频分析完成后再对照')
                    self.compare_pair(job,left,right)
                else:self.discover(job)
                self.store.job_status(job['id'],'completed','已完成')
            except InterruptedError:
                self.store.job_status(job['id'],'queued','上次中断，等待继续')
            except Exception as e:
                self.store.job_status(job['id'],'failed','处理失败',str(e))
                if job['kind']=='process':self.store.update_video(job['video_id'],status='failed',error=str(e))
                if job['creator_id']:self.store.creator_error(job['creator_id'],str(e))
