import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from uibe.analysis import normalize,chunks,parse_json
from uibe.store import Store
from uibe.server import create_app
from uibe.comparison import normalize as normalize_comparison,candidates


class AppTests(unittest.TestCase):
    def test_manual_discovery_import_keeps_creator_and_reuses_existing_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(tmp,start_worker=False);s=app.state.engine.store
            cid=s.add_creator('https://www.douyin.com/user/known-sec-uid','已关注的作者')
            rows=[{'video_id':str(7695692306247499738+i),'published_at':100+i,'title':'已发现视频'} for i in range(2)]
            s.save_discovery(cid,{'videos':rows,'complete':True,'checked_at_epoch':200})
            existing=app.state.engine.import_links('https://www.douyin.com/video/'+rows[1]['video_id'])[0]
            s.update_video(existing['id'],author_name='已***者',author_hash='stable-hash')
            with TestClient(app) as client:
                for i,row in enumerate(rows):
                    url=f"/api/creators/{cid}/videos/{row['video_id']}/import"
                    response=client.post(url)
                    self.assertEqual(response.status_code,200)
                    result=response.json()[0];video=s.video(result['id'])
                    self.assertEqual(result['created'],i==0)
                    self.assertEqual(video['author_id'],'known-sec-uid')
                    self.assertEqual(video['author_name'],'已关注的作者')
                    self.assertEqual(video['published_at'],row['published_at'])
                    self.assertEqual(client.post(url).status_code,404)
                self.assertEqual(s.video(existing['id'])['author_hash'],'stable-hash')
                self.assertEqual(len(s.all('videos')),2)
                self.assertEqual(len(s.all('jobs')),2)
                self.assertEqual(s.pending_discoveries(cid),[])

    def test_same_masked_creator_is_not_a_cross_author_candidate(self):
        analysis={'events':[{'name':'美国国债规模'}],'claims':[{'statement':'测试主张'}]}
        current={'id':'a','author_id':'known-sec-uid','author_hash':'same','analysis':analysis}
        same={'id':'b','author_hash':'same','analysis':analysis}
        different={'id':'c','author_hash':'different','analysis':analysis}
        unknown={'id':'d','analysis':None}
        self.assertEqual([v['id'] for v in candidates(current,[same,different,unknown])],['c'])

    def test_queue_restart_and_duplicate_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp)
            a,created=s.add_video(title='test',sha256='abc');self.assertTrue(created)
            b,created=s.add_video(title='same',sha256='abc');self.assertEqual(a,b);self.assertFalse(created)
            j=s.enqueue('process',video_id=a);self.assertEqual(j,s.enqueue('process',video_id=a))
            self.assertEqual(s.claim_job()['id'],j);s.recover();self.assertEqual(s.claim_job()['id'],j)
            s.job_status(j,'failed','失败','offline')
            self.assertNotEqual(j,s.enqueue('process',video_id=a))

    def test_concurrent_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp)
            with ThreadPoolExecutor(4) as pool:
                ids=list(pool.map(lambda _:s.add_video(title='test',sha256='same')[0],range(8)))
            self.assertEqual(len(set(ids)),1)

    def test_discovery_failure_preserves_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);c=s.add_creator('https://www.douyin.com/user/test','test')
            s.save_discovery(c,{'videos':[{'video_id':'123','published_at':90,'title':'x'}],'complete':True,'checked_at_epoch':100})
            s.save_discovery(c,{'videos':[{'video_id':'456','published_at':190,'title':'y'}],'complete':False,'checked_at_epoch':200})
            self.assertEqual(s.creator(c)['checkpoint'],100)
            s.creator_error(c,'network failure');self.assertEqual(s.creator(c)['checkpoint'],100)
            self.assertEqual(len(s.pending_discoveries(c)),2)
            s.mark_discovery_queued(c,'123');self.assertEqual(len(s.pending_discoveries(c)),1)

    def test_analysis_cannot_invent_quote_or_citation(self):
        seg=[{'id':1,'text':'预计短期回落'},{'id':2,'text':'长期仍不确定'}]
        raw={'relevant':True,'title':'test','summary':'','events':[{'name':'走势讨论','segment_ids':[1]}],
             'claims':[{'kind':'博主预测','statement':'短期可能回落','segment_ids':[1]}]}
        result=normalize(raw,seg);self.assertEqual(result['claims'][0]['evidence'][0]['quote'],'预计短期回落')
        raw['claims'][0]['segment_ids']=[99]
        with self.assertRaises(ValueError):normalize(raw,seg)

    def test_chunks_cover_whole_transcript(self):
        seg=[{'id':i,'text':'x'*40} for i in range(150)]
        flattened=[s['id'] for c in chunks(seg,max_chars=600) for s in c]
        self.assertEqual(flattened,list(range(150)))

    def test_comparison_requires_same_event_and_real_references(self):
        video={'analysis':{'claims':[{'statement':'短期回落'}]}}
        result={'same_event':False,'relation':'分歧','event':'黄金','reason':'','left_claim_ids':[1],'right_claim_ids':[1],'limitations':[]}
        with self.assertRaises(ValueError):normalize_comparison(result,video,video)
        result.update(same_event=True,relation='相近',left_claim_ids=[5])
        with self.assertRaises(ValueError):normalize_comparison(result,video,video)
        result.update(same_event=False,relation='无法比较',left_claim_ids=[],right_claim_ids=[])
        self.assertEqual(normalize_comparison(result,video,video)['relation'],'无法比较')

    def test_api_boundaries_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(tmp,start_worker=False)
            with TestClient(app) as client:
                self.assertEqual(client.get('/').status_code,200)
                self.assertEqual(client.post('/api/import/upload?filename=x.exe',content=b'x').status_code,400)
                self.assertEqual(client.post('/api/settings',json={'values':{}},headers={'origin':'https://evil.example'}).status_code,403)
                self.assertEqual(client.get('/api/videos/missing/media').status_code,404)
                r=client.post('/api/import/links',json={'text':'https://www.douyin.com/video/7695692306247499738'})
                self.assertEqual(r.status_code,200)
                again=client.post('/api/import/links',json={'text':'https://www.douyin.com/video/7695692306247499738'})
                self.assertFalse(again.json()['videos'][0]['created'])
                self.assertEqual(len(client.get('/api/state').json()['jobs']),1)
                self.assertEqual(client.post('/api/settings',json={'values':{'monitor_interval_minutes':1}}).status_code,400)

    def test_brief_and_comparison_keep_original_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(tmp,start_worker=False);s=app.state.engine.store
            path=Path(tmp)/'analysis.json'
            evidence={'segment_id':1,'quote':'原文甲'}
            data={'events':[{'name':'事件甲','date':'','assets':[],'segment_ids':[1]}],
                  'claims':[{'statement':'首次分析','evidence':[evidence]}]}
            path.write_text(json.dumps(data))
            a,_=s.add_video(title='甲',analysis_path=str(path));b,_=s.add_video(title='乙',analysis_path=str(path))
            s.update_video(a,status='ready');s.update_video(b,status='ready')
            s.save_comparison(a,b,{'relation':'相近','left_claim_ids':[1],'right_claim_ids':[1]})
            data['claims'][0]['statement']='重新分析';path.write_text(json.dumps(data))
            with TestClient(app) as client:
                self.assertEqual(len(client.get('/api/brief').json()['events']),2)
                result=client.get('/api/videos/'+a).json()['comparisons'][0]
                self.assertEqual(result['left_claims'][0]['statement'],'首次分析')
                self.assertEqual(result['right_claims'][0]['evidence'][0]['quote'],'原文甲')
                pair=client.post('/api/compare',json={'left_id':a,'right_id':b})
                again=client.post('/api/compare',json={'left_id':b,'right_id':a})
                self.assertEqual(pair.json()['job_id'],again.json()['job_id'])
                self.assertEqual(client.post('/api/compare',json={'left_id':a,'right_id':a}).status_code,400)

    def test_empty_claims_cannot_enter_comparison_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(tmp,start_worker=False);s=app.state.engine.store
            path=Path(tmp)/'analysis.json';path.write_text(json.dumps({'claims':[],'events':[]}))
            a,_=s.add_video(title='没有明确主张',analysis_path=str(path))
            b,_=s.add_video(title='另一条视频',analysis_path=str(path))
            for id in [a,b]:s.update_video(id,status='ready')
            with TestClient(app) as client:
                response=client.post('/api/compare',json={'left_id':a,'right_id':b})
                self.assertEqual(response.status_code,400)
                self.assertIn('没有可用于对照的主张',response.json()['detail'])
                self.assertEqual(client.get('/api/state').json()['jobs'],[])

    def test_reimport_restores_missing_source_without_losing_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(tmp,start_worker=False);s=app.state.engine.store
            with TestClient(app) as client:
                first=client.post('/api/import/upload?filename=a.mp4',content=b'media').json()
                video=s.video(first['id']);Path(video['source_path']).unlink()
                s.update_video(first['id'],status='ready')
                again=client.post('/api/import/upload?filename=b.mp4',content=b'media').json()
                self.assertEqual(again['id'],first['id']);self.assertFalse(again['created'])
                self.assertEqual(Path(s.video(first['id'])['source_path']).read_bytes(),b'media')
                self.assertEqual(s.video(first['id'])['status'],'ready')


if __name__=='__main__':unittest.main()
