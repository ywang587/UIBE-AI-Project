"""Integration checks with a fake external process, never reported as model quality."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uibe.engine import Engine
from uibe.store import now
from uibe.engine import sha256


class EngineIntegrationTests(unittest.TestCase):
    def test_long_analysis_gets_more_time_than_single_chunk(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(tmp);source=Path(tmp)/'sample.mp4';source.write_bytes(b'media fixture')
            vid,_=e.import_file(source);job=e.store.claim_job();digest=sha256(source)
            transcript=Path(tmp)/'complete.json'
            transcript.write_text(json.dumps({'source':{'sha256':digest},'settings':{'model':'medium'},
                'segments':[{'id':i+1,'text':'宏观经济背景讨论'*12,'start':i*5,'end':(i+1)*5} for i in range(120)]}))
            e.store.update_video(vid,transcript_path=str(transcript));budgets=[]
            def fake_command(args,log,timeout):
                self.assertIn('uibe.model_worker',args);budgets.append(timeout)
                Path(args[args.index('--output')+1]).write_text(json.dumps({'source_sha256':digest,'relevant':True}))
            with patch.object(e,'command',side_effect=fake_command):e.process(job)
            self.assertEqual(len(budgets),1)
            self.assertGreater(budgets[0],1800)
            self.assertEqual(e.store.video(vid)['status'],'ready')

    def test_start_rechecks_even_inside_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(tmp);e.save_settings({'monitor_enabled':True})
            cid=e.store.add_creator('https://www.douyin.com/user/test','test')
            e.store.save_discovery(cid,{'videos':[],'complete':True,'checked_at_epoch':123})
            with patch('threading.Thread'):
                e.start()
            jobs=e.store.all('jobs')
            self.assertEqual(len(jobs),1);self.assertEqual(jobs[0]['creator_id'],cid)
            e.close()

    def test_second_instance_cannot_reset_active_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=Engine(tmp);second=Engine(tmp)
            with patch('threading.Thread'):first.start()
            try:
                vid,_=first.store.add_video(title='test')
                job_id=first.store.enqueue('process',video_id=vid);first.store.claim_job()
                with self.assertRaises(RuntimeError):second.start()
                self.assertEqual(first.store.all('jobs')[0]['status'],'running')
            finally:first.close()
            with patch('threading.Thread'):second.start()
            self.assertEqual(second.store.all('jobs')[0]['status'],'queued')
            second.close()

    def test_discovery_queues_once_and_failed_run_does_not_read_old_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(tmp);e.save_settings({'auto_process_discoveries':True})
            cid=e.store.add_creator('https://www.douyin.com/user/test','test')
            jid=e.store.enqueue('discover',creator_id=cid);job=e.store.claim_job()
            data={'videos':[{'video_id':'7695692306247499738','published_at':90,'title':'title'}],'complete':True,'checked_at_epoch':100}
            def fake_command(args,log,timeout):
                Path(args[-1]).write_text(json.dumps(data))
            with patch.object(e,'command',side_effect=fake_command):e.discover(job)
            self.assertEqual(len(e.store.all('videos')),1)
            self.assertEqual(len([j for j in e.store.all('jobs') if j['kind']=='process']),1)
            with patch.object(e,'command',side_effect=fake_command):e.discover(job)
            self.assertEqual(len([j for j in e.store.all('jobs') if j['kind']=='process']),1)
            with patch.object(e,'command',side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):e.discover(job)
            self.assertFalse((e.root/'creators'/cid/'discovery.json').exists())
            self.assertEqual(e.store.creator(cid)['checkpoint'],100)

    def test_changed_asr_model_does_not_reuse_old_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(tmp);source=Path(tmp)/'sample.mp4';source.write_bytes(b'media fixture')
            vid,_=e.import_file(source);job=e.store.claim_job();digest=sha256(source)
            old=Path(tmp)/'old.json';old.write_text(json.dumps({'source':{'sha256':digest},'settings':{'model':'small'},'segments':[]}))
            e.store.update_video(vid,transcript_path=str(old))
            calls=[]
            def fake_command(args,log,timeout=3600):
                calls.append([str(a) for a in args]);output=Path(args[args.index('--output')+1])
                if 'uibe.model_worker' in args:
                    output.write_text(json.dumps({'source_sha256':digest,'relevant':True}))
                else:
                    target=output/'complete'/'transcript.json';target.parent.mkdir(parents=True)
                    target.write_text(json.dumps({'source':{'sha256':digest},'settings':{'model':'medium'},'segments':[{'id':1,'text':'测试'}]}))
                    # A newer cache from a different model must not win by mtime.
                    wrong=output/'wrong-model'/'transcript.json';wrong.parent.mkdir()
                    wrong.write_text(json.dumps({'source':{'sha256':digest},'settings':{'model':'small'},'segments':[]}))
                    os.utime(wrong,(2000000000,2000000000))
            with patch.object(e,'command',side_effect=fake_command):e.process(job)
            self.assertEqual(len(calls),2)
            self.assertTrue(any('transcribe.py' in part for part in calls[0]))
            self.assertNotEqual(e.store.video(vid)['transcript_path'],str(old))
            self.assertEqual(json.loads(Path(e.store.video(vid)['transcript_path']).read_text())['settings']['model'],'medium')
            self.assertEqual(json.loads(old.read_text())['settings']['model'],'small')

    def test_masked_download_metadata_preserves_known_creator(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(tmp);dyid='7693573120950603018'
            vid,_=e.store.add_video(douyin_id=dyid,title='等待下载',author_name='已关注的作者',author_id='known-sec-uid')
            e.store.enqueue('process',video_id=vid);job=e.store.claim_job()
            def fake_command(args,log,timeout=3600):
                output=Path(args[args.index('--output')+1])
                if 'uibe.model_worker' in args:
                    output.write_text(json.dumps({'source_sha256':sha256(Path(e.store.video(vid)['source_path'])),'relevant':True}))
                elif any('probe_download.py' in str(x) for x in args):
                    media=output/'dy/media'/dyid/'video.mp4';media.parent.mkdir(parents=True);media.write_bytes(b'media')
                    meta=output/'douyin/jsonl/details.jsonl';meta.parent.mkdir(parents=True)
                    meta.write_text(json.dumps({'aweme_id':dyid,'desc':'标题','nickname':'已***者','creator_hash':'stable-hash','create_time':100}))
                else:
                    target=output/'complete/transcript.json';target.parent.mkdir(parents=True)
                    target.write_text(json.dumps({'source':{'sha256':sha256(Path(e.store.video(vid)['source_path']))},'settings':{'model':'medium'},'segments':[]}))
            with patch.object(e,'command',side_effect=fake_command):e.process(job)
            result=e.store.video(vid)
            self.assertEqual(result['author_name'],'已关注的作者')
            self.assertEqual(result['author_id'],'known-sec-uid')
            self.assertEqual(result['author_hash'],'stable-hash')

if __name__=='__main__':unittest.main()
