"""Compare grounded claims without confusing assets, dates or horizons."""
import json
from .analysis import parse_json
PROMPT_VERSION='comparison-v4-coexistence'

SYSTEM='''你只比较两份视频分析中已经附有原文依据的主张，不能提出自己的市场机制。相同资产不等于同一事件。先检查是否是同一具体事件、事件时期、问题、前提和预测期限。资料不足可以不能比较，不要硬造冲突。相同时间同一问题相反判断才构成分歧；短期下跌和长期上涨不是冲突。不同作者说法一致不证明事实。
输入主张带从1开始的 claim_id。输出一个 JSON：
{"same_event":true,"same_question":true,"comparable_horizons":true,"comparable_conditions":true,"event":"具体事件或未确定","reason":"先说明日期、期限、条件是否可比","left_claim_ids":[1],"right_claim_ids":[1],"relation":"相近|分歧|互补|无法比较","limitations":["未解决问题"]}
先检查比较维度，再决定 relation。短期预测与长期预测的 comparable_horizons 必须为 false，即使方向相反也不得标为分歧。双方都不是预测时，该字段可为 true。条件缺失但会影响结论时 comparable_conditions=false；双方同样没有附加条件时可为 true。分歧必须同时满足同一事件、同一问题、可比期限和可比条件，不满足时可以互补或无法比较。
same_event=false 时 relation 必须是无法比较。不能比较时引文编号可以为空。可比较时双方必须至少引用一项真实主张。禁止把不明日期补为视频发布日期。不要使用其他知识。'''
SYSTEM+='''
决定关系前，必须回答：双方选中的说法在同一世界中是否可以同时成立？输出 coexistence，取值为“可以同时成立”“同条件下相互排斥”“依据不足”。
只有直接相互排斥的判断才是分歧；不能因为主题、侧重、语气或例子不同就判分歧。找不到明确相反判断时选互补、相近或无法比较。
例：“支出很大所以借债”和“借新债偿还到期旧债”可以同时成立，是不同方面的解释；不能称为矛盾。
例：“目前经济强”和“如果未来增长不足，需要承担债务代价”可以同时成立。后者的条件没有发生，不是否定前者。
例：同一时期、同一条件下的“价格将上涨”和“价格将下跌”才是相互排斥。短期跌与长期涨、条件不同的预测都不是。
历史数据和支出数字不是预测期限；不要把支出年份解释为对经济走势的预测期。说明应直接比较双方实际引用的说法，不能只罗列主题然后宣称矛盾。'''


def payload(left,right,selected=None,question=None):
    def compact(video,side):
        a=video['analysis']
        evidence_ids={e['segment_id'] for i,c in enumerate(a['claims'],1)
                      if selected is None or i in selected[side] for e in c['evidence']}
        return {'title':video['title'],'author_name':video.get('author_name'),
                'published_at':video.get('published_at'),'events':[e for e in a.get('events',[])
                    if selected is None or evidence_ids.intersection(e.get('segment_ids',[]))],
                'claims':[{'claim_id':i+1,**{k:c[k] for k in
                    ['kind','statement','time_horizon','conditions','evidence','limitation','candidate_kinds','classification_note'] if k in c}}
                    for i,c in enumerate(a['claims']) if selected is None or i+1 in selected[side]]}
    return [{'role':'system','content':SYSTEM},
            {'role':'user','content':json.dumps({'question':question,'left':compact(left,'left'),'right':compact(right,'right')},ensure_ascii=False)}]


def normalize(raw,left,right):
    if type(raw.get('same_event')) is not bool:raise ValueError('缺少同事件判断')
    if raw.get('relation') not in {'相近','分歧','互补','无法比较'}:raise ValueError('不支持的比较类型')
    if not raw['same_event'] and raw['relation']!='无法比较':raise ValueError('不同事件不能直接比较')
    if raw['relation']=='分歧' and not all(raw.get(k) is True for k in ['same_question','comparable_horizons','comparable_conditions']):
        raise ValueError('分歧必须是同一问题且期限、条件可比；短期下跌和长期上涨不构成分歧，请改为互补或无法比较')
    if raw['relation']=='分歧' and raw.get('coexistence')!='同条件下相互排斥':
        raise ValueError('说法可以同时成立或依据不足时不能判为分歧；请重新检查双方实际判断')
    for side,video in [('left',left),('right',right)]:
        ids=raw.get(side+'_claim_ids')
        if not isinstance(ids,list) or any(type(i) is not int or i<1 or i>len(video['analysis']['claims']) for i in ids):
            raise ValueError('比较引用不存在的主张')
        if raw['relation']!='无法比较' and not ids:raise ValueError('比较必须有双方依据')
    return {k:raw[k] for k in ['same_event','relation','event','reason','left_claim_ids','right_claim_ids','limitations']} | {k:raw.get(k) for k in ['same_question','comparable_horizons','comparable_conditions','coexistence']}


def source_bound_result(result,left,right,question):
    """Display only the relation and source checks, never a newly generated mechanism."""
    result=dict(result)
    result['model_draft']={k:result[k] for k in ['event','reason','limitations','comparable_horizons','comparable_conditions']}
    claims={side:[video['analysis']['claims'][i-1] for i in result[side+'_claim_ids']]
            for side,video in [('left',left),('right',right)]}
    def field_set(side,key,predictions=False):
        return {c.get(key,'未说明').strip() for c in claims[side]
                if (not predictions or c['kind']=='博主预测') and c.get(key,'未说明').strip() not in {'','未说明'}}
    conditions=[field_set(s,'conditions') for s in ['left','right']]
    horizons=[field_set(s,'time_horizon',True) for s in ['left','right']]
    predictions=[any(c['kind']=='博主预测' for c in claims[s]) for s in ['left','right']]
    if conditions[0]!=conditions[1]:result['comparable_conditions']=False
    if any(predictions) and (not all(predictions) or not all(horizons) or horizons[0]!=horizons[1]):
        result['comparable_horizons']=False
    uncertain=not all(result.get(k) is True for k in ['same_question','comparable_horizons','comparable_conditions'])
    if result['relation']=='分歧' and uncertain:result['relation']='无法比较'
    labels={'相近':'模型认为这些主张表达相近的判断。','互补':'模型认为双方从不同方面展开，这些说法可以同时成立。',
            '分歧':'模型认为双方在相同问题与前提下作出了相互排斥的判断。',
            '无法比较':'现有依据不足以作出同一问题、期限和条件下的直接对照。'}
    result['event']=question or '未确定'
    result['reason']=labels[result['relation']]+('所选主张的期限或条件未确认一致，不能据此认定预测一致或相反。' if uncertain else '')+'下列内容逐条保留双方原话，请据此核对。'
    result['limitations']=['关系标签仍是模型判断，选取的主张可能遗漏相关内容；共同问题不代表具体事件日期已核实。',
                            '未对博主数据或解释作独立事实核查；不同主张的类别与引用范围仍可能有误。']
    result['presentation_version']='source-bound-comparison-v1'
    return result


def candidates(current,others,limit=2):
    def bigrams(text):return {text[i:i+2] for i in range(len(text)-1) if text[i:i+2].strip()}
    a=current['analysis'];query=bigrams(' '.join(e['name'] for e in a.get('events',[])))
    if not query or not a.get('claims'):return []
    ranked=[]
    for other in others:
        if current['id']==other['id'] or not (other.get('analysis') or {}).get('claims'):continue
        if current.get('author_id') and current['author_id']==other.get('author_id'):continue
        if current.get('author_hash') and current['author_hash']==other.get('author_hash'):continue
        tokens=bigrams(' '.join(e['name'] for e in other['analysis'].get('events',[])))
        score=len(query & tokens)/max(1,len(query | tokens))
        if score>=.06:ranked.append((score,other))
    return [x[1] for x in sorted(ranked,key=lambda x:x[0],reverse=True)[:limit]]
