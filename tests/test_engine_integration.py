"""Integration checks with a fake external process, never reported as model quality."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uibe.engine import Engine
from uibe.store import now


class EngineIntegrationTests(unittest.TestCase):
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

if __name__=='__main__':unittest.main()
