"""Optional dated official background; never input to blogger-claim extraction."""
from datetime import date,datetime,timezone
from decimal import Decimal,InvalidOperation
import json
import hashlib
import re
from urllib.parse import urlencode
from urllib.request import urlopen

DATASET='https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/'
ENDPOINT='https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny'
FIELDS=['record_date','debt_held_public_amt','intragov_hold_amt','tot_pub_debt_out_amt']


def eligible(analysis,title=''):
    if analysis.get('relevant') is False:return False
    text=title+' '+ ' '.join(c['statement'] for c in analysis.get('claims',[]))
    return bool(re.search(r'美国|美國|美债|美債',text) and re.search(r'债务|債務|万亿|萬億|规模|規模|国债总|國債總',text))


def fetch_us_debt(as_of=None,timeout=15):
    today=datetime.now(timezone.utc).date()
    boundary=date.fromisoformat(as_of) if as_of else today
    if boundary>today:raise ValueError('背景资料的记录日期上限不能在未来')
    url=ENDPOINT+'?'+urlencode({'fields':','.join(FIELDS),'filter':f'record_date:lte:{boundary.isoformat()}',
                                'sort':'-record_date','page[size]':'1'})
    with urlopen(url,timeout=timeout) as response:
        raw=response.read(1_000_001)
    if len(raw)>1_000_000:raise ValueError('官方接口响应超出预期大小')
    data=json.loads(raw)
    if not data.get('data'):raise ValueError('官方接口在所选日期之前没有返回数据')
    row=data['data'][0];record_date=date.fromisoformat(row['record_date'])
    if record_date>boundary:raise ValueError('官方记录晚于所选日期，拒绝混用')
    try:amounts={field:Decimal(row[field]) for field in FIELDS[1:]}
    except (InvalidOperation,KeyError,TypeError) as error:raise ValueError('官方金额字段无效') from error
    if any(not v.is_finite() or v<0 for v in amounts.values()):raise ValueError('官方金额字段无效')
    if abs(amounts['debt_held_public_amt']+amounts['intragov_hold_amt']-amounts['tot_pub_debt_out_amt'])>Decimal('0.02'):
        raise ValueError('官方总额与分项不一致，需复核')
    record_url=ENDPOINT+'?'+urlencode({'fields':','.join(FIELDS),'filter':f'record_date:eq:{record_date.isoformat()}','page[size]':'1'})
    return {'kind':'external_background','status':'available','source':'美国财政部 Fiscal Data',
            'title':'美国联邦债务规模与构成','dataset_url':DATASET,'data_url':record_url,'query_url':url,
            'record_sha256':hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest(),
            'record_date':record_date.isoformat(),'requested_as_of':boundary.isoformat(),
            'retrieved_at':datetime.now(timezone.utc).isoformat(),
            'unit':'USD','values':{k:format(v,'f') for k,v in amounts.items()},
            'scope':'财政部记录的联邦债务总额由公众持有债务与政府内部持有债务组成。',
            'limitation':'这是带日期的外部背景，可能晚于视频事件；不代表当时已知信息，也不证明博主的因果解释。'}


def supplement(analysis,title='',fetcher=None):
    if not eligible(analysis,title):return analysis
    result=dict(analysis)
    try:background=(fetcher or fetch_us_debt)()
    except Exception as error:
        background={'kind':'external_background','status':'unavailable','source':'美国财政部 Fiscal Data',
            'title':'美国联邦债务规模与构成','dataset_url':DATASET,
            'retrieved_at':datetime.now(timezone.utc).isoformat(),
            'error':f'{type(error).__name__}: {error}'[:300],
            'limitation':'本次未取得外部背景；这不表示博主主张正确或错误。'}
    result['external_background']=[background]
    return result
