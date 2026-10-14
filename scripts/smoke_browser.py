"""Portable browser regression using generated media and clearly synthetic records."""
import argparse
import asyncio
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from uibe.store import Store


def fixture(root):
    import av
    import numpy as np
    media=root/'synthetic.mp4'
    with av.open(str(media),'w') as out:
        stream=out.add_stream('libx264',rate=10);stream.width=320;stream.height=180;stream.pix_fmt='yuv420p'
        for i in range(60):
            pixels=np.zeros((180,320,3),dtype=np.uint8);pixels[:,:,1]=80+i*2
            for packet in stream.encode(av.VideoFrame.from_ndarray(pixels,format='rgb24')):out.mux(packet)
        for packet in stream.encode():out.mux(packet)
    store=Store(root/'app');creator=store.add_creator('https://www.douyin.com/user/synthetic','合成作者')
    store.save_discovery(creator,{'videos':[{'video_id':'123','title':'合成生活片段','published_at':1}],
                                  'complete':True,'checked_at_epoch':2})
    unrelated,_=store.add_video(title='合成生活片段',douyin_id='123')
    store.update_video(unrelated,status='irrelevant');store.mark_discovery_queued(creator,'123')
    texts=['市場風險需要核對。','條件尚未確定。','這是合成測試資料。','保留完整原話。']
    transcript={'segments':[{'id':i+1,'text':text,'start':float(i),'end':float(i+1)} for i,text in enumerate(texts)]}
    claims=[{'kind':'博主解释','statement':text,'evidence':[{'segment_id':i+1,'quote':text}],
             'conditions':'未说明','time_horizon':'未说明','limitation':'合成資料'} for i,text in enumerate(texts)]
    analysis={'relevant':True,'title':'合成財經片段','summary':'合成测试','summary_source_claim_ids':[1,2,3],
              'claims':claims,'events':[],'limitations':['合成测试，不是实际模型输出'],'method':'synthetic fixture'}
    for name,data in [('analysis',analysis),('transcript',transcript)]:
        (root/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False))
    vid,_=store.add_video(title='合成財經片段',source_path=str(media),
                         analysis_path=str(root/'analysis.json'),transcript_path=str(root/'transcript.json'))
    store.update_video(vid,status='ready')
    return vid,unrelated,transcript


async def check(base,vid,unrelated,original,output):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        try:
            page=await browser.new_page(viewport={'width':1440,'height':960});errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            await page.goto(base);await page.wait_for_selector('#video-grid .card')
            assert await page.locator('#video-grid .card').count()==1
            assert await page.locator('#video-count').inner_text()=='1'
            await page.locator('[data-tab="creators"]').click()
            assert await page.locator(f'#creator-list [data-video="{unrelated}"]').count()==1
            await page.locator('[data-tab="library"]').click()
            await page.locator(f'#video-grid [data-video="{vid}"]').click()
            await page.wait_for_selector('.key-points')
            assert await page.locator('.key-points > li').count()==3
            assert '市场风险' in await page.locator('.key-points').inner_text()
            assert not await page.locator('.archived-claim').first.is_visible()
            await page.locator('.claim-archive > summary').click()
            assert await page.locator('.archived-claim').count()==4
            assert await page.locator('.archived-claim').first.is_visible()
            await page.locator('.claim-archive > summary').click()
            await page.locator('.key-points details summary').nth(1).click()
            await page.locator('.key-points .seek').nth(1).click()
            await page.wait_for_function('document.querySelector("video").currentTime>1.2')
            assert await page.locator('video').evaluate('(v)=>v.readyState>=2&&v.videoWidth>0')
            downloaded=await (await page.request.get(base+f'/api/videos/{vid}/transcript')).json()
            assert downloaded==original
            await page.screenshot(path=str(output/'desktop.png'),full_page=True)
            await page.set_viewport_size({'width':390,'height':844})
            assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            await page.screenshot(path=str(output/'mobile.png'),full_page=True)
            assert not errors,errors
            return {'passed':True,'scope':'synthetic browser regression; no inference',
                    'checks':['irrelevant_hidden','update_retained','three_points','expand_full_analysis',
                              'simplified_display','raw_download_preserved','media_seek_play','mobile_width'],
                    'browser_errors':errors}
        finally:await browser.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'local_data/browser-smoke')
    args=p.parse_args();output=args.output.resolve()
    if output.exists():p.error('输出目录已存在，请使用新的 --output')
    output.mkdir(parents=True);report={'passed':False};proc=None
    try:
        with tempfile.TemporaryDirectory(prefix='uibe-browser-') as tmp:
            root=Path(tmp);vid,unrelated,original=fixture(root)
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            base=f'http://127.0.0.1:{port}'
            with (output/'server.log').open('w') as log:
                command='import sys,uvicorn;from uibe.server import create_app;uvicorn.run(create_app(sys.argv[1],start_worker=False),host="127.0.0.1",port=int(sys.argv[2]))'
                proc=subprocess.Popen([sys.executable,'-c',command,str(root/'app'),str(port)],cwd=ROOT,stdout=log,stderr=log)
                try:
                    for _ in range(100):
                        if proc.poll() is not None:raise RuntimeError('预览服务退出，查看 server.log')
                        try:
                            with urllib.request.urlopen(base+'/api/state',timeout=1):break
                        except OSError:time.sleep(.1)
                    else:raise TimeoutError('预览服务启动超时')
                    report=asyncio.run(check(base,vid,unrelated,original,output))
                finally:
                    proc.terminate()
                    try:proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
    except Exception as error:
        report['error']=f'{type(error).__name__}: {error}';raise
    finally:
        (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print('报告：',output/'report.json')


if __name__=='__main__':main()
