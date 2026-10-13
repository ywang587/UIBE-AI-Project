"""Compare grounded claims without confusing assets, dates or horizons."""
import json
from .analysis import parse_json
PROMPT_VERSION='comparison-v2-dimensions'

SYSTEM='''你只比较两份视频分析中已经附有原文依据的主张，不能提出自己的市场机制。相同资产不等于同一事件。先检查是否是同一具体事件、事件时期、问题、前提和预测期限。资料不足可以不能比较，不要硬造冲突。相同时间同一问题相反判断才构成分歧；短期下跌和长期上涨不是冲突。不同作者说法一致不证明事实。
输入主张带从1开始的 claim_id。输出一个 JSON：
{"same_event":true,"same_question":true,"comparable_horizons":true,"comparable_conditions":true,"event":"具体事件或未确定","reason":"先说明日期、期限、条件是否可比","left_claim_ids":[1],"right_claim_ids":[1],"relation":"相近|分歧|互补|无法比较","limitations":["未解决问题"]}
先检查比较维度，再决定 relation。短期预测与长期预测的 comparable_horizons 必须为 false，即使方向相反也不得标为分歧。双方都不是预测时，该字段可为 true。条件缺失但会影响结论时 comparable_conditions=false；双方同样没有附加条件时可为 true。分歧必须同时满足同一事件、同一问题、可比期限和可比条件，不满足时可以互补或无法比较。
same_event=false 时 relation 必须是无法比较。不能比较时引文编号可以为空。可比较时双方必须至少引用一项真实主张。禁止把不明日期补为视频发布日期。不要使用其他知识。'''


def payload(left,right):
    def compact(video):
        a=video['analysis']
        return {'title':video['title'],'author_name':video.get('author_name'),
                'published_at':video.get('published_at'),'events':a.get('events',[]),
                'claims':[{'claim_id':i+1,**{k:c[k] for k in
                    ['kind','statement','time_horizon','conditions','evidence','limitation'] if k in c}}
                    for i,c in enumerate(a['claims'])]}
    return [{'role':'system','content':SYSTEM},
            {'role':'user','content':json.dumps({'left':compact(left),'right':compact(right)},ensure_ascii=False)}]


def normalize(raw,left,right):
    if type(raw.get('same_event')) is not bool:raise ValueError('缺少同事件判断')
    if raw.get('relation') not in {'相近','分歧','互补','无法比较'}:raise ValueError('不支持的比较类型')
    if not raw['same_event'] and raw['relation']!='无法比较':raise ValueError('不同事件不能直接比较')
    if raw['relation']=='分歧' and not all(raw.get(k) is True for k in ['same_question','comparable_horizons','comparable_conditions']):
        raise ValueError('分歧必须是同一问题且期限、条件可比；短期下跌和长期上涨不构成分歧，请改为互补或无法比较')
    for side,video in [('left',left),('right',right)]:
        ids=raw.get(side+'_claim_ids')
        if not isinstance(ids,list) or any(type(i) is not int or i<1 or i>len(video['analysis']['claims']) for i in ids):
            raise ValueError('比较引用不存在的主张')
        if raw['relation']!='无法比较' and not ids:raise ValueError('比较必须有双方依据')
    return {k:raw[k] for k in ['same_event','relation','event','reason','left_claim_ids','right_claim_ids','limitations']} | {k:raw.get(k) for k in ['same_question','comparable_horizons','comparable_conditions']}


def candidates(current,others,limit=2):
    def bigrams(text):return {text[i:i+2] for i in range(len(text)-1) if text[i:i+2].strip()}
    a=current['analysis'];query=bigrams(' '.join(e['name'] for e in a.get('events',[])))
    if not query or not a.get('claims'):return []
    ranked=[]
    for other in others:
        if current['id']==other['id'] or not other.get('analysis',{}).get('claims'):continue
        if current.get('author_id') and current['author_id']==other.get('author_id'):continue
        tokens=bigrams(' '.join(e['name'] for e in other['analysis'].get('events',[])))
        score=len(query & tokens)/max(1,len(query | tokens))
        if score>=.06:ranked.append((score,other))
    return [x[1] for x in sorted(ranked,key=lambda x:x[0],reverse=True)[:limit]]
