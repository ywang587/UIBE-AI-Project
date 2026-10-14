import json
import unittest
from uibe.comparison_focus import select_sources
from uibe.comparison import payload,normalize,source_bound_result
from uibe.structured import comparison_schema


class FocusTests(unittest.TestCase):
    def videos(self):
        def video(title):
            return {'title':title,'analysis':{'claims':[
                {'kind':'分类待复核','statement':'冲突标签','evidence':[{'segment_id':1,'quote':'冲突标签'}]},
                {'kind':'博主解释','statement':'如果增长更快，债务比例可以下降','conditions':'如果增长更快',
                 'evidence':[{'segment_id':2,'quote':'如果增长更快，债务比例可以下降'}]},
                {'kind':'博主评价','statement':'其他主题','evidence':[{'segment_id':3,'quote':'其他主题'}]}],
                'events':[{'name':'增长与债务','segment_ids':[2]},{'name':'其他主题','segment_ids':[3]}]}}
        return video('第一位作者'),video('第二位作者')

    def test_separate_selection_keeps_original_ids_and_complete_selected_evidence(self):
        left,right=self.videos();calls=[]
        outputs=iter(['{"shared_question":true,"question":"增长与债务","reason":"双方讨论此问题"}',
                      '{"claim_ids":[2,2]}','{"claim_ids":[3]}'])
        def generate(messages,schema,**kwargs):
            calls.append(json.loads(messages[1]['content']));return next(outputs)
        focus,selected=select_sources(generate,left,right)
        self.assertEqual(selected,{'left':[2],'right':[3]})
        self.assertEqual([c['claim_id'] for c in calls[1]['claims']],[2,3])
        self.assertEqual(calls[1]['title'],'第一位作者');self.assertEqual(calls[2]['title'],'第二位作者')
        data=json.loads(payload(left,right,selected,focus['question'])[1]['content'])
        self.assertEqual(data['left']['claims'][0]['claim_id'],2)
        self.assertEqual(data['right']['claims'][0]['claim_id'],3)
        self.assertEqual(data['left']['claims'][0]['evidence'],left['analysis']['claims'][1]['evidence'])
        self.assertEqual(data['left']['events'],[left['analysis']['events'][0]])
        schema=comparison_schema(left,right,selected)
        result={'same_event':True,'same_question':True,'comparable_horizons':True,'comparable_conditions':True,
                'event':'增长与债务','reason':'测试','left_claim_ids':[2],'right_claim_ids':[3],
                'relation':'相近','coexistence':'可以同时成立','limitations':[]}
        schema.model_validate(result)
        with self.assertRaises(ValueError):schema.model_validate({**result,'right_claim_ids':[2]})
        with self.assertRaises(ValueError):normalize({**result,'relation':'分歧'},left,right)

    def test_no_shared_question_skips_claim_selection(self):
        left,right=self.videos();calls=[]
        def generate(*args,**kwargs):
            calls.append(1);return '{"shared_question":false,"question":"未确定","reason":"不同问题"}'
        focus,selected=select_sources(generate,left,right)
        self.assertFalse(focus['shared_question']);self.assertEqual(len(calls),1)
        self.assertEqual(selected,{'left':[],'right':[]})

    def test_conflicting_or_nonexistent_claim_cannot_be_selected(self):
        left,right=self.videos()
        for id in [1,99]:
            responses=iter(['{"shared_question":true,"question":"增长","reason":"共同问题"}',json.dumps({'claim_ids':[id]})])
            with self.assertRaises(ValueError):select_sources(lambda *a,**k:next(responses),left,right)

    def test_missing_counterpart_condition_cannot_be_reported_as_comparable_prediction(self):
        left,right=self.videos()
        left['analysis']['claims'][1].update(kind='博主预测',time_horizon='明天')
        right['analysis']['claims'][1].update(kind='博主事实性主张',conditions='未说明',time_horizon='2026年')
        raw={'same_event':True,'same_question':True,'comparable_horizons':True,'comparable_conditions':True,
             'left_claim_ids':[2],'right_claim_ids':[2],'relation':'分歧','event':'预算年份被写成预测',
             'reason':'新增的市场机制','limitations':['不可靠解释'],'coexistence':'同条件下相互排斥'}
        result=source_bound_result(raw,left,right,'债务问题')
        self.assertEqual(result['relation'],'无法比较')
        self.assertFalse(result['comparable_horizons']);self.assertFalse(result['comparable_conditions'])
        self.assertNotIn('新增的市场机制',result['reason']);self.assertNotIn('不可靠解释',result['limitations'])
        self.assertEqual(result['model_draft']['reason'],raw['reason'])
        self.assertEqual(result['left_claim_ids'],[2]);self.assertEqual(raw['relation'],'分歧')


if __name__=='__main__':unittest.main()
