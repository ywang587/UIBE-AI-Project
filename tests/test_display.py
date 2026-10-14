import json
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from uibe.display import reading_copy
from uibe.server import create_app


class DisplayTests(unittest.TestCase):
    def test_reading_copy_preserves_identifiers_paths_and_source(self):
        data={'title':'經濟風險','assets':['國債'],
              'source_path':'/資料/經濟.mp4','original_url':'https://example.test/經濟',
              'claims':[{'statement':'市場變化','evidence':[{'segment_id':9,'quote':'風險上升'}]}]}
        converted=reading_copy(data)
        self.assertEqual(converted['title'],'经济风险')
        self.assertEqual(converted['assets'],['国债'])
        self.assertEqual(converted['claims'][0]['evidence'][0],{'segment_id':9,'quote':'风险上升'})
        self.assertEqual(converted['source_path'],data['source_path'])
        self.assertEqual(converted['original_url'],data['original_url'])
        self.assertEqual(data['claims'][0]['evidence'][0]['quote'],'風險上升')

    def test_simplified_detail_keeps_original_downloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(tmp,start_worker=False);store=app.state.engine.store
            analysis={'title':'經濟','claims':[{'statement':'風險上升','evidence':[{'segment_id':1,'quote':'風險上升'}]}]}
            transcript={'segments':[{'id':1,'start':0,'end':2,'text':'風險上升'}]}
            paths={}
            for name,value in [('analysis',analysis),('transcript',transcript)]:
                path=Path(tmp)/(name+'.json');path.write_text(json.dumps(value,ensure_ascii=False));paths[name+'_path']=str(path)
            vid,_=store.add_video(title='經濟',**paths)
            with TestClient(app) as client:
                original=client.get('/api/videos/'+vid).json()
                display=client.get('/api/videos/'+vid+'?simplified=true').json()
                self.assertEqual(original['analysis']['claims'][0]['statement'],'風險上升')
                self.assertEqual(display['analysis']['claims'][0]['statement'],'风险上升')
                self.assertEqual(display['transcript']['segments'][0]['text'],'风险上升')
                self.assertEqual(display['transcript_path'],original['transcript_path'])
                self.assertEqual(client.get('/api/videos/'+vid+'/analysis').json(),analysis)
                self.assertEqual(client.get('/api/videos/'+vid+'/transcript').json(),transcript)
                self.assertEqual(json.loads(Path(paths['analysis_path']).read_text()),analysis)

    def test_imported_irrelevant_video_remains_in_update_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(tmp,start_worker=False);store=app.state.engine.store
            cid=store.add_creator('https://www.douyin.com/user/known','作者')
            store.save_discovery(cid,{'videos':[{'video_id':'123','title':'生活','published_at':50}],
                                     'complete':True,'checked_at_epoch':60})
            result=app.state.engine.import_discovery(store.creator(cid),store.pending_discoveries(cid)[0])
            store.update_video(result['id'],status='irrelevant')
            self.assertEqual(store.pending_discoveries(cid),[])
            with TestClient(app) as client:
                row=client.get('/api/state').json()['discoveries'][cid][0]
                self.assertEqual(row['local_video_id'],result['id'])
                self.assertEqual(row['status'],'irrelevant')
                self.assertEqual(row['queued'],1)
                self.assertEqual(row['published_at'],50)


if __name__=='__main__':unittest.main()
