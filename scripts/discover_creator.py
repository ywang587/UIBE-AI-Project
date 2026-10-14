"""Bounded creator discovery using MediaCrawler's existing session.

No media downloads, no login attempts. A partial scan does not advance checkpoint.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('crawler',type=Path)
    p.add_argument('creator')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--since',type=int,default=0)
    p.add_argument('--max-pages',type=int,default=3)
    a=p.parse_args();crawler=a.crawler.resolve(strict=True);output=a.output.resolve()
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(crawler/'.browsers'))
    os.environ.setdefault('MPLCONFIGDIR',str(crawler/'.matplotlib'))
    os.chdir(crawler);sys.path.insert(0,str(crawler))
    import config
    from media_platform.douyin.core import DouYinCrawler
    from media_platform.douyin.help import parse_creator_info_from_url
    from media_platform.douyin.login import DouYinLogin
    secid=parse_creator_info_from_url(a.creator).sec_user_id
    config.PLATFORM='dy';config.CRAWLER_TYPE='creator';config.HEADLESS=True
    config.ENABLE_CDP_MODE=False;config.ENABLE_GET_COMMENTS=False;config.ENABLE_GET_MEDIA=False
    async def no_login(self):raise RuntimeError('UIBE_LOGIN_REQUIRED: 请先在正常下载入口登录抖音')
    DouYinLogin.begin=no_login
    result={'videos':[],'complete':False,'checked_at_epoch':int(time.time()),'pages':0,'since':a.since}
    class DiscoveryCrawler(DouYinCrawler):
        async def get_creators_and_videos(self):
            cursor='';seen=set();seen_cursors=set()
            for _ in range(max(1,min(a.max_pages,10))):
                response=await self.dy_client.get_user_aweme_posts(secid,cursor)
                if 'has_more' not in response or 'aweme_list' not in response:
                    raise RuntimeError('作品列表响应缺少必要字段，不能记为检查成功')
                result['pages']+=1
                posts=response['aweme_list'] or []
                for row in posts:
                    vid=str(row.get('aweme_id') or '')
                    if not vid or vid in seen:continue
                    seen.add(vid)
                    published=row.get('create_time')
                    if published is None:raise RuntimeError('作品缺少发布时间，检查点不前移')
                    if published<a.since:continue
                    author=row.get('author') or {}
                    result['videos'].append({'video_id':vid,'title':row.get('desc',''),
                                              'published_at':published,'author_name':author.get('nickname'),
                                              'author_id':author.get('sec_uid') or author.get('uid'),
                                              'url':'https://www.douyin.com/video/'+vid})
                if not response['has_more']:
                    result['complete']=True;break
                cursor=str(response.get('max_cursor') or '')
                if not posts or not cursor or cursor in seen_cursors:
                    raise RuntimeError('作品分页没有前进，检查点不前移')
                seen_cursors.add(cursor)
                # A full page strictly before the boundary is only a best-effort boundary.
                # Surface this distinction rather than claiming historical completeness.
                if a.since and all(p.get('create_time',a.since)>=0 and p.get('create_time',a.since)<a.since for p in posts):
                    result['complete']=True
                    result['boundary_basis']='整页早于回查边界；平台排序和删除仍可能影响覆盖'
                    break
                await asyncio.sleep(3)
    async def execute():
        runner=DiscoveryCrawler()
        try:await runner.start()
        finally:
            if getattr(runner,'browser_context',None):
                from playwright.async_api import Error
                try: await runner.browser_context.close()
                except Error: pass
    asyncio.run(execute())
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('discovery',len(result['videos']),'complete',result['complete'])


if __name__=='__main__':main()
