"""Probe one MediaCrawler video using an existing session; stop if login is needed."""
import argparse
import os
from pathlib import Path
import runpy
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('crawler', type=Path)
    p.add_argument('video_id')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--metadata-only',action='store_true',help='Read public video details without downloading media again')
    a=p.parse_args()
    if not a.video_id.isdigit():
        p.error('video_id must contain digits only')
    crawler=a.crawler.resolve(strict=True)
    output=a.output.resolve()
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(crawler/'.browsers'))
    os.environ.setdefault('MPLCONFIGDIR',str(crawler/'.matplotlib'))
    os.chdir(crawler)
    sys.path.insert(0,str(crawler))
    from media_platform.douyin.login import DouYinLogin
    async def stop_for_login(self):
        raise RuntimeError('UIBE_LOGIN_REQUIRED: existing session unavailable; manual login required')
    DouYinLogin.begin=stop_for_login
    sys.argv=['main.py','--platform','dy','--lt','qrcode','--type','detail',
              '--specified_id',a.video_id,'--headless','true','--get_media','false' if a.metadata_only else 'true',
              '--get_comment','false','--save_data_path',str(output)]
    runpy.run_path(str(crawler/'main.py'),run_name='__main__')


if __name__ == '__main__':
    main()
