import unittest
import json
from uibe.analysis import normalize,combine,numeric_tokens
from uibe.extraction import extract_part


class GroundingTests(unittest.TestCase):
    def raw(self,claim,events=None):
        if events is None:
            reference={'span':dict(claim['span'])} if 'span' in claim else {'segment_ids':list(claim['segment_ids'])}
            events=[{'name':'测试讨论问题','date':'',**reference}]
        return {'relevant':True,'title':'测试材料','claims':[claim],
                'events':events,'summary':'未引用的新机制不应进入摘要'}

    def test_complete_span_keeps_numbers_after_fourth_asr_fragment(self):
        texts=['本轮政策调整','从2022年3月','到2023年7月','持续16个月','累计525个基点','共11次']
        segments=[{'id':i+1,'start':i*3,'end':i*3+3,'text':text} for i,text in enumerate(texts)]
        claim={'span':{'start_id':1,'end_id':6},'kind':'博主事实性主张',
               'statement':'从2022年3月到2023年7月共11次调整，累计525个基点',
               'time_horizon':'从2022年3月到2023年7月','conditions':'未说明'}
        result=normalize(self.raw(claim),segments)
        self.assertEqual(len(result['claims'][0]['evidence']),6)
        self.assertEqual(result['claims'][0]['evidence'][-1]['quote'],'共11次')
        claim['span']['end_id']=4
        with self.assertRaisesRegex(ValueError,'未被当前引文覆盖的数字'):normalize(self.raw(claim),segments)

    def test_unstated_date_condition_and_horizon_rejected(self):
        segments=[{'id':1,'text':'如果政策落实，未来三个月人民币可能升值'}]
        claim={'span':{'start_id':1,'end_id':1},'kind':'博主预测','statement':'人民币可能升值',
               'time_horizon':'未来三个月','conditions':'如果政策落实'}
        self.assertEqual(normalize(self.raw(claim),segments)['claims'][0]['conditions'],'如果政策落实')
        claim['conditions']='美元走弱'
        with self.assertRaisesRegex(ValueError,'条件不是当前引文'):normalize(self.raw(claim),segments)
        claim['conditions']='未说明';claim['time_horizon']='未来一年'
        with self.assertRaisesRegex(ValueError,'期限不是当前引文'):normalize(self.raw(claim),segments)
        claim['time_horizon']='未说明'
        event={'span':{'start_id':1,'end_id':1},'name':'政策与汇率','date':'2026年10月13日','assets':['人民币']}
        with self.assertRaisesRegex(ValueError,'事件日期不是当前引文'):normalize(self.raw(claim,[event]),segments)

    def test_summary_cannot_add_unquoted_generation(self):
        part=normalize(self.raw({'segment_ids':[1],'kind':'博主事实性主张','statement':'储备减少'}),[{'id':1,'text':'储备减少'}])
        result=combine([part],{'source':{'sha256':'test'}},'test-model',1)
        self.assertEqual(result['summary'],'博主所述：储备减少')
        self.assertEqual(result['summary_source_claim_ids'],[1])

    def test_invalid_or_unbounded_spans_rejected(self):
        segments=[{'id':1,'text':'前文','start':0,'end':2},{'id':2,'text':'后文','start':99,'end':101}]
        claim={'kind':'博主评价','statement':'情况复杂','span':{'start_id':1,'end_id':2}}
        with self.assertRaisesRegex(ValueError,'超过90秒'):normalize(self.raw(claim),segments)
        claim['span']={'start_id':2,'end_id':1}
        with self.assertRaisesRegex(ValueError,'顺序错误'):normalize(self.raw(claim),segments)
        claim['span']={'start_id':1,'end_id':9}
        with self.assertRaisesRegex(ValueError,'不存在'):normalize(self.raw(claim),segments)

    def test_numeric_values_not_substrings_or_new_arithmetic(self):
        self.assertEqual(numeric_tokens('1,000万、2.90%'),{'1000','2.9%'})
        claim={'kind':'博主事实性主张','statement':'结果是1.5亿','segment_ids':[1]}
        with self.assertRaises(ValueError):normalize(self.raw(claim),[{'id':1,'text':'结果是11.5亿'}])
        claim['statement']='降低50%'
        with self.assertRaises(ValueError):normalize(self.raw(claim),[{'id':1,'text':'从20降到10'}])

    def test_invalid_sibling_does_not_erase_valid_claim(self):
        segments=[{'id':1,'text':'本月出售股份获得65亿美元','start':0,'end':5},
                  {'id':2,'text':'如果找不到钱，未来可能关门','start':5,'end':10}]
        base={'time_range_quote':'未说明','explicit_if_quote':'未说明','limitation':'尚未外部核查'}
        good={**base,'span':{'start_id':1,'end_id':1},'statement':'出售股份获得65亿美元'}
        bad={**base,'span':{'start_id':2,'end_id':2},'statement':'已经关门','explicit_if_quote':'如果政策失败'}
        draft={'title':'2024年出售资产','facts':[good],'predictions':[bad],'explanations':[],'evaluations':[],'promotions':[]}
        outputs=iter([draft,{'claim':None},{'events':[{'span':{'start_id':1,'end_id':1},'name':'股份出售','date':'本月','assets':[]}]}])
        def generate(*args,**kwargs):return json.dumps(next(outputs),ensure_ascii=False)
        result=extract_part(generate,segments,{})
        self.assertEqual([c['statement'] for c in result['claims']],[good['statement']])
        self.assertEqual(result['title'],'视频解读')
        self.assertEqual(result['withheld_claims'][0]['draft_statement'],'已经关门')
        merged=combine([result],{'source':{'sha256':'test'}},'test',0)
        self.assertNotIn('已经关门',merged['summary'])
        self.assertEqual(len(merged['withheld_claims']),1)


if __name__=='__main__':unittest.main()
