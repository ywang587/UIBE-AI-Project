import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from course_urls import canonical, extract, load_course_urls
from evidence_report import validate
from check_download import read_jsonl
from repair_course import repair
from transcribe import timestamp, validate_segments, run

ID = '7695692306247499738'
URL = 'https://www.douyin.com/video/' + ID


class PipelineTests(unittest.TestCase):
    def test_mixed_share_and_short_deduplicate(self):
        text = f'财经分享 https://www.douyin.com/share/video/{ID}/?mid=123 中文！ https://v.douyin.com/abc/\n{URL}。'
        self.assertEqual(extract(text, resolver=lambda _: URL), [URL])

    def test_spoofed_domain_ignored(self):
        self.assertEqual(extract('https://evil.example/douyin.com/video/'+ID), [])
        with self.assertRaises(ValueError):
            canonical('https://douyin.com.evil.example/video/'+ID)

    def test_modal(self):
        self.assertEqual(canonical('https://www.douyin.com/user/test?modal_id='+ID), URL)

    def test_short_failure_is_explicit(self):
        def fail(_):
            raise TimeoutError('network unavailable')
        with self.assertRaises(TimeoutError):
            extract('https://v.douyin.com/abc/', resolver=fail)

    def test_moved_directory_and_gb_encoding(self):
        with tempfile.TemporaryDirectory(prefix='uibe 中文 ') as tmp:
            p=Path(tmp)/'sub';p.mkdir()
            (p/'links.txt').write_bytes(('分享 '+URL).encode('gb18030'))
            (p/'transcript.txt').write_text('没有链接', encoding='utf-8')
            self.assertEqual(load_course_urls(tmp), [URL])

    def test_jsonl_unicode_line_separator_in_caption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'metadata.jsonl'
            row={'aweme_id':ID, 'desc':'宏观\u2028经济\u2029分析'}
            path.write_text(json.dumps(row,ensure_ascii=False)+'\n',encoding='utf-8')
            self.assertEqual(read_jsonl(path),[row])

    def test_repair_in_another_directory_preserves_originals(self):
        with tempfile.TemporaryDirectory(prefix='另一台设备 ') as tmp:
            root=Path(tmp)
            (root/'MediaCrawler/config').mkdir(parents=True)
            (root/'outputs').mkdir()
            config=root/'MediaCrawler/config/base_config.py'
            original="SAVE_DATA_PATH = '/old/machine/output'\n"
            config.write_text(original,encoding='utf-8')
            notebook={'cells':[{'cell_type':'code','source':['old'], 'outputs':[], 'execution_count':None} for _ in range(3)]}
            for name in ['视频转文字.ipynb','outputs/视频转文字_单视频测试.ipynb']:
                (root/name).write_text(json.dumps(notebook),encoding='utf-8')
            repair(root)
            self.assertNotIn('/old/machine',config.read_text())
            self.assertEqual(config.with_name(config.name+'.before-portability').read_text(),original)
            self.assertIn('UIBE_CRAWLER_DIR',(root/'outputs/启动抖音视频下载.command').read_text())
            repair(root)
            self.assertEqual(config.with_name(config.name+'.before-portability').read_text(),original)

    def test_timestamp_rollover(self):
        self.assertEqual(timestamp(59.9996),'00:01:00,000')

    def test_empty_or_invalid_transcript_rejected(self):
        for rows in [[], [{'start': 3, 'end': 2, 'text': 'bad'}], [{'start': 0, 'end': 1, 'text': ''}]]:
            with self.assertRaises(ValueError):
                validate_segments(rows, 5)

    def test_quotes_and_wrong_source_rejected(self):
        t={'source': {'sha256':'abc'}, 'segments':[{'id':1,'text':'油价上升'}]}
        a={'source_sha256':'abc','method':'synthetic test','claims':[{'kind':'博主解释','statement':'油价上升','evidence':[{'segment_id':1,'quote':'油价上升'}]}]}
        validate(t,a)
        wrong=copy.deepcopy(a);wrong['source_sha256']='other'
        with self.assertRaises(ValueError):validate(t,wrong)
        wrong=copy.deepcopy(a);wrong['claims'][0]['evidence'][0]['quote']='降息'
        with self.assertRaises(ValueError):validate(t,wrong)

    def test_missing_input_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'out'
            with self.assertRaises(FileNotFoundError):run(Path(tmp)/'missing.mp4', target)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
