"""Extract and deduplicate Douyin video links from course TXT files."""
import os
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

HOSTS = {'douyin.com', 'www.douyin.com', 'm.douyin.com', 'v.douyin.com', 'www.iesdouyin.com', 'iesdouyin.com'}


def canonical(url):
    p = urlparse(url)
    if p.scheme not in {'http', 'https'} or p.hostname not in HOSTS or p.username or p.password:
        raise ValueError('不是受支持的抖音链接')
    match = re.search(r'/(?:share/)?video/(\d{15,22})(?:/|$)', p.path)
    ids = parse_qs(p.query).get('modal_id', [])
    video_id = match.group(1) if match else (ids[0] if ids else '')
    if re.fullmatch(r'\d{15,22}', video_id):
        return 'https://www.douyin.com/video/' + video_id
    raise ValueError('链接中没有视频 ID')


class DouyinRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).hostname not in HOSTS:
            raise ValueError('短链接跳转到非抖音域名，停止解析')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def resolve_short(url):
    p = urlparse(url)
    if p.hostname != 'v.douyin.com' or p.scheme not in {'http', 'https'}:
        raise ValueError('不是抖音短链接')
    opener = build_opener(DouyinRedirects())
    with opener.open(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as response:
        return canonical(response.url)


def extract(text, resolver=resolve_short):
    result = []
    for url in re.findall(r'https?://[^\s<>，。；！！？、\u2028\u2029]+', text):
        url = url.rstrip(')）]】,.;!"\'')
        try:
            value = canonical(url)
        except ValueError:
            if urlparse(url).hostname == 'v.douyin.com':
                value = canonical(resolver(url))
            elif urlparse(url).hostname in HOSTS:
                raise ValueError(f'无法识别视频链接：{url}')
            else:
                continue
        if value not in result:
            result.append(value)
    return result


def load_course_urls(source_dir=None):
    # In MediaCrawler/config this default points to the sibling course materials.
    default = Path(__file__).resolve().parents[2] / '测试视频'
    source = Path(source_dir or os.environ.get('UIBE_VIDEO_LINKS_DIR', default)).expanduser()
    results = []
    for path in sorted(source.rglob('*.txt')):
        data = path.read_bytes()
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = data.decode('gb18030')
        for url in extract(text):
            if url not in results:
                results.append(url)
    if not results:
        raise ValueError(f'TXT 文件中未找到有效视频链接：{source}')
    return results
