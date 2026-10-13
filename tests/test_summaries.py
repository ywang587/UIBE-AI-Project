import json
import unittest
from uibe.summaries import select_summary


class SummaryTests(unittest.TestCase):
    def analysis(self):
        return {'relevant':True,'title':'讨论债务压力','summary':'旧摘要','summary_source_claim_ids':[1],
                'claims':[{'kind':'博主事实性主张','statement':'开头例子'},
                          {'kind':'分类待复核','statement':'分类冲突的说法'},
                          {'kind':'博主解释','statement':'增长有助于减轻债务压力'},
                          {'kind':'博主预测','statement':'如果增长不足，债务压力可能上升','conditions':'如果增长不足'}],
                'provenance':{'source_version':'retained'}}

    def test_selection_can_use_end_of_video_without_rewriting_conditions(self):
        original=self.analysis();captured=[]
        def generate(messages,schema,**kwargs):
            sent=json.loads(messages[1]['content']);captured.extend(sent['claims'])
            return '{"claim_ids":[3,4,3]}'
        result=select_summary(generate,original)
        self.assertEqual(result['summary_source_claim_ids'],[3,4])
        self.assertEqual(result['summary'],'博主所述：增长有助于减轻债务压力；如果增长不足，债务压力可能上升')
        self.assertNotIn(2,[c['claim_id'] for c in captured])
        self.assertEqual(result['claims'],original['claims'])
        self.assertEqual(original['summary'],'旧摘要')
        self.assertEqual(result['provenance']['source_version'],'retained')

    def test_invalid_ids_conflicting_kind_and_new_prose_never_enter_summary(self):
        for raw in ['{"claim_ids":[99]}','{"claim_ids":[2]}',
                    '{"claim_ids":[3],"summary":"新增机制"}','{"claim_ids":[1,3,4,1]}']:
            with self.subTest(raw=raw):
                original=self.analysis();result=select_summary(lambda *a,**kw:raw,original)
                self.assertEqual(result['summary_source_claim_ids'],[])
                self.assertEqual(result['provenance']['summary_selection_status'],'failed')
                self.assertEqual(result['claims'],original['claims'])
                self.assertNotIn('新增机制',result['summary'])

    def test_selection_failure_and_irrelevance_preserve_analysis(self):
        def failed(*args,**kwargs):raise RuntimeError('local inference failed')
        original=self.analysis();result=select_summary(failed,original)
        self.assertEqual(result['claims'],original['claims'])
        self.assertEqual(result['provenance']['summary_selection_status'],'failed')
        original['relevant']=False
        self.assertEqual(select_summary(failed,original),original)


if __name__=='__main__':unittest.main()
