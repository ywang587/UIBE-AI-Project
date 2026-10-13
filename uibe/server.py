"""Personal local application. Run with python -m uibe.server."""
from contextlib import asynccontextmanager
import argparse
import json
import os
from pathlib import Path
import uuid
from urllib.parse import urlparse
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .engine import Engine,REPO


def create_app(data_root=None,start_worker=True):
    engine=Engine(data_root or os.environ.get('UIBE_DATA_DIR',REPO/'local_data/app'))
    @asynccontextmanager
    async def life(app):
        if start_worker:engine.start()
        yield
        if start_worker:engine.close()
    app=FastAPI(lifespan=life);app.state.engine=engine
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','testserver'])
    @app.middleware('http')
    async def same_origin(request,call_next):
        origin=request.headers.get('origin')
        if request.method not in {'GET','HEAD','OPTIONS'} and origin and urlparse(origin).netloc!=request.headers.get('host'):
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'来源不匹配'},status_code=403)
        return await call_next(request)
    @app.exception_handler(ValueError)
    async def invalid(request,error):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':str(error)},status_code=400)

    def get_video(id):
        r=engine.store.video(id)
        if not r:raise HTTPException(404,'视频不存在')
        return r

    @app.get('/')
    def index():return FileResponse(REPO/'web/index.html')
    @app.get('/app.js')
    def script():return FileResponse(REPO/'web/app.js',media_type='text/javascript')
    @app.get('/style.css')
    def style():return FileResponse(REPO/'web/style.css',media_type='text/css')
    @app.get('/api/state')
    def state():
        return {'videos':engine.store.all('videos'),'jobs':engine.store.all('jobs'),
                'creators':engine.store.all('creators'),'settings':engine.settings,
                'discoveries':{c['id']:engine.store.pending_discoveries(c['id']) for c in engine.store.all('creators')},
                'comparisons':engine.store.all('comparisons')}
    @app.get('/api/brief')
    def brief():
        rows=[]
        for video in engine.store.all('videos'):
            path=video.get('analysis_path')
            if video['status']!='ready' or not path or not Path(path).exists():continue
            analysis=json.loads(Path(path).read_text())
            for event in analysis.get('events',[]):
                ids=set(event.get('segment_ids',[]))
                claims=[c for c in analysis['claims'] if ids.intersection(e['segment_id'] for e in c['evidence'])]
                rows.append({'video_id':video['id'],'video_title':video['title'],'author':video['author_name'],
                             'event':event,'claims':claims,'published_at':video['published_at']})
        return {'events':rows,'scope':'所选博主与已导入内容，不是完整市场新闻'}
    @app.get('/api/videos/{id}')
    def detail(id):
        r=get_video(id)
        for name in ['transcript','analysis']:
            path=r.get(name+'_path')
            r[name]=json.loads(Path(path).read_text()) if path and Path(path).exists() else None
        comparisons=[]
        seen=set()
        for c in engine.store.all('comparisons'):
            if id not in {c['left_id'],c['right_id']}:continue
            pair=tuple(sorted([c['left_id'],c['right_id']]))
            if pair in seen:continue
            seen.add(pair)
            data=json.loads(c['result_json'])
            item={**c,'result':data}
            for side in ['left','right']:
                snapshot=data.get('sources',{}).get(side)
                if snapshot is not None:
                    item[side+'_title']=snapshot['title'];item[side+'_claims']=snapshot['claims']
                    continue
                source=engine.store.video(c[side+'_id'])
                item[side+'_title']=source['title'] if source else '原视频不可用'
                ap=source.get('analysis_path') if source else None
                claims=json.loads(Path(ap).read_text()).get('claims',[]) if ap and Path(ap).exists() else []
                item[side+'_claims']=[claims[i-1] for i in data.get(side+'_claim_ids',[]) if 0<i<=len(claims)]
            comparisons.append(item)
        r['comparisons']=comparisons
        return r
    @app.get('/api/videos/{id}/media')
    def media(id):
        r=get_video(id);path=Path(r['source_path']) if r['source_path'] else None
        if not path or not path.is_file():raise HTTPException(404,'原视频不可用')
        return FileResponse(path)
    @app.get('/api/videos/{id}/transcript')
    def transcript_download(id):
        r=get_video(id)
        if not r['transcript_path']:raise HTTPException(404,'转录尚未完成')
        return FileResponse(r['transcript_path'],filename='transcript.json',media_type='application/json')
    @app.get('/api/videos/{id}/analysis')
    def analysis_download(id):
        r=get_video(id)
        if not r['analysis_path']:raise HTTPException(404,'分析尚未完成')
        return FileResponse(r['analysis_path'],filename='analysis.json',media_type='application/json')

    class Links(BaseModel):text:str
    class Pair(BaseModel):left_id:str;right_id:str
    @app.post('/api/compare')
    def compare(body:Pair):
        if body.left_id==body.right_id:raise ValueError('请选择两条不同视频')
        left=get_video(body.left_id);right=get_video(body.right_id)
        if left['status']!='ready' or right['status']!='ready':raise ValueError('只能对照两条已完成的财经视频')
        for video in [left,right]:
            path=video.get('analysis_path')
            if not path or not Path(path).exists() or not json.loads(Path(path).read_text()).get('claims'):
                raise ValueError('这条视频没有可用于对照的主张，请先查看原文和待复核内容')
        return {'job_id':engine.store.enqueue('compare',video_id=left['id'],other_video_id=right['id'])}
    @app.post('/api/import/links')
    def links(body:Links):return {'videos':engine.import_links(body.text)}
    @app.post('/api/import/upload')
    async def upload(request:Request,filename:str):
        name=Path(filename).name
        if Path(name).suffix.lower() not in {'.mp4','.mov','.mkv','.webm','.m4a','.mp3','.wav'}:raise ValueError('不支持的媒体格式')
        folder=engine.root/'uploads'/uuid.uuid4().hex;folder.mkdir(parents=True)
        path=folder/name;size=0
        try:
            with path.open('wb') as f:
                async for block in request.stream():
                    size+=len(block)
                    if size>2*1024**3:raise ValueError('单个文件不能超过 2GB')
                    f.write(block)
            if not size:raise ValueError('文件为空')
            id,created=engine.import_file(path)
            if not created and engine.store.video(id)['source_path']!=str(path):path.unlink();folder.rmdir()
            return {'id':id,'created':created}
        except BaseException:
            if path.exists():path.unlink()
            if folder.exists():folder.rmdir()
            raise
    @app.post('/api/videos/{id}/retry')
    def retry(id):
        r=get_video(id)
        job=engine.store.enqueue('process',video_id=id)
        engine.store.update_video(id,status='queued',error=None)
        return {'job_id':job}
    class Creator(BaseModel):url:str;name:str='关注博主'
    @app.post('/api/creators')
    def add_creator(body:Creator):
        import re
        match=re.fullmatch(r'https?://(?:www\.|m\.)?douyin\.com/(?:share/)?user/([A-Za-z0-9_-]+)(?:\?.*)?',body.url.strip())
        raw=body.url.strip()
        if match:sec=match.group(1)
        elif re.fullmatch(r'MS4w[A-Za-z0-9_-]+',raw):sec=raw
        else:raise ValueError('请输入抖音博主主页链接或 sec_uid；显示的抖音号不一定是采集标识')
        id=engine.store.add_creator('https://www.douyin.com/user/'+sec,body.name[:80])
        engine.store.enqueue('discover',creator_id=id)
        return {'id':id}
    @app.post('/api/creators/{id}/check')
    def check_creator(id):
        if not engine.store.creator(id):raise HTTPException(404,'博主不存在')
        return {'job_id':engine.store.enqueue('discover',creator_id=id)}
    @app.post('/api/creators/{id}/videos/{video_id}/import')
    def import_discovery(id,video_id):
        rows=engine.store.pending_discoveries(id)
        row=next((x for x in rows if x['video_id']==video_id),None)
        creator=engine.store.creator(id)
        if row is None or creator is None:raise HTTPException(404,'未找到该发现记录')
        return [engine.import_discovery(creator,row)]
    class Settings(BaseModel):values:dict
    @app.post('/api/settings')
    def settings(body:Settings):engine.save_settings(body.values);return {'ok':True}
    @app.get('/api/jobs/{id}/log')
    def log(id):
        job=next((x for x in engine.store.all('jobs') if x['id']==id),None)
        if not job:raise HTTPException(404,'任务不存在')
        folder=engine.root/('videos' if job['video_id'] else 'creators')/(job['video_id'] or job['creator_id'])
        run=folder/'runs'/job['id']
        if run.is_dir():folder=run
        files=sorted(list(folder.glob('*.log'))+list((engine.root/'comparisons'/job['id']).glob('*.log')),key=lambda p:p.stat().st_mtime)
        return {'text':files[-1].read_text(errors='replace')[-8000:] if files else '尚无运行记录'}
    return app


if __name__=='__main__':
    import uvicorn
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',type=int,default=7860)
    p.add_argument('--data-dir',type=Path)
    p.add_argument('--open-browser',action='store_true')
    a=p.parse_args()
    if a.open_browser:
        import threading,webbrowser
        def show_when_ready():
            import time,urllib.request
            url=f'http://127.0.0.1:{a.port}'
            for _ in range(40):
                try:
                    with urllib.request.urlopen(url+'/api/state',timeout=1) as response:
                        if response.status==200:webbrowser.open(url);return
                except OSError:pass
                time.sleep(.25)
        threading.Thread(target=show_when_ready,daemon=True).start()
    uvicorn.run(create_app(a.data_dir),host='127.0.0.1',port=a.port)
