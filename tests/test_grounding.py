import unittest
import json
from uibe.analysis import normalize,combine,numeric_tokens,reconcile_categories
from uibe.extraction import extract_part
from uibe.source_fields import time_quotes,amount_only


class GroundingTests(unittest.TestCase):
    def test_conflicting_labels_keep_one_claim_and_original_evidence(self):
        claim={'kind':'博主事实性主张','statement':'去年储备减少',
               'time_horizon':'去年','conditions':'未说明',
               'evidence':[{'segment_id':1,'quote':'去年储备减少'}]}
        future={**claim,'kind':'博主预测'}
        other={**claim,'statement':'市场认为风险偏高','kind':'博主评价',
               'evidence':[{'segment_id':2,'quote':'市场认为风险偏高'}]}
        part={'relevant':True,'title':'储备讨论','claims':[claim,future,other],
              'events':[],'limitations':[],'asr_issues':[]}
        result=combine([part],{'source':{'sha256':'test'}},'test-model',1)
        self.assertEqual(len(result['claims']),2)
        first=result['claims'][0]
        self.assertEqual(first['kind'],'分类待复核')
        self.assertEqual(first['candidate_kinds'],['博主事实性主张','博主预测'])
        self.assertEqual(first['evidence'],claim['evidence'])
        self.assertEqual(claim['kind'],'博主事实性主张')
        self.assertEqual(result['summary_source_claim_ids'],[2])
        self.assertNotIn('去年储备减少',result['summary'])
        self.assertEqual(reconcile_categories(result['claims']),result['claims'])
        from uibe.comparison import payload
        video={'title':'测试','analysis':result}
        sent=json.loads(payload(video,video)[1]['content'])
        self.assertIn('classification_note',sent['left']['claims'][0])

    def test_different_context_or_conditions_are_not_merged_as_label_conflicts(self):
        first={'kind':'博主解释','statement':'经济增长缓解债务压力',
               'time_horizon':'未说明','conditions':'如果增长更快',
               'evidence':[{'segment_id':1,'quote':'如果增长更快，经济增长缓解债务压力'}]}
        other={**first,'kind':'博主预测','conditions':'如果利率下降'}
        elsewhere={**first,'kind':'博主预测','evidence':[{'segment_id':8,'quote':'经济增长缓解债务压力'}]}
        self.assertEqual(reconcile_categories([first,other,elsewhere]),[first,other,elsewhere])

    def test_time_expressions_are_not_conditions_or_conclusions(self):
        quote='要是再不想办法筹钱的话，公务员工资可能发不出来，政府可能关门'
        segments=[{'id':1,'text':quote}]
        claim={'kind':'博主预测','statement':quote,'span':{'start_id':1,'end_id':1},
               'time_horizon':quote,'conditions':'要是再不想办法筹钱的话'}
        with self.assertRaisesRegex(ValueError,'不能把条件'):normalize(self.raw(claim),segments,strict_fields=True)
        claim['time_horizon']='未说明'
        self.assertEqual(normalize(self.raw(claim),segments)['claims'][0]['conditions'],'要是再不想办法筹钱的话')
        for phrase in ['不到一个月','这半年','未来三个月','过去17年','从2022年3月到2023年7月',
                       '2026年10月1日','2026年第三季度','近3-5年','长期']:
            with self.subTest(phrase=phrase):self.assertIn(phrase,time_quotes([{'text':phrase}]))

    def test_amounts_are_not_asset_names(self):
        for value in ['65亿美元','6.5%','三万亿卢比','百分之十','1,000万元']:
            self.assertTrue(amount_only(value),value)
        for value in ['美元','国企股份','标普500指数','纳斯达克100指数','10年期美债']:
            self.assertFalse(amount_only(value),value)
        segments=[{'id':1,'text':'出售国企股份获得65亿美元'}]
        claim={'kind':'博主事实性主张','statement':'出售国企股份获得65亿美元','segment_ids':[1]}
        events=[{'name':'股份出售','assets':['65亿美元'],'segment_ids':[1]}]
        with self.assertRaisesRegex(ValueError,'资产名称不能填金额'):normalize(self.raw(claim,events),segments,strict_fields=True)

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
