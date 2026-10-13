"""Conservative Chinese surface forms, never inferred dates or financial facts."""
import re

NUMBER=r'(?:\d+(?:\.\d+)?|[零〇一二三四五六七八九十百千万萬亿億两兩半]+)'
DATE=r'(?:\d{4}年(?:\d{1,2}月(?:\d{1,2}[日号])?)?|\d{1,2}月(?:\d{1,2}[日号])?)'
TIME=re.compile(
    rf'(?:从|自)?{DATE}(?:到|至|—|－|-){DATE}'
    rf'|(?:\d{{4}}年)?第{NUMBER}季度'
    rf'|{DATE}'
    rf'|(?:未来|未來|今后|今後|接下来|接下來|过去|過去|最近|近|约)?{NUMBER}(?:至|到|-|—){NUMBER}(?:个|個)?(?:年|季度|月|周|週|天)(?:内|以来|之后)?'
    rf'|(?:未来|未來|今后|今後|接下来|接下來|过去|過去|最近|近|不到|超过|大约|约|至少|至多|这|那|前|后)?{NUMBER}(?:个|個)?(?:世纪|年|季度|月|周|週|星期|天|日|小时|小時|分钟|分鐘)(?:的时间之内|以内|以来|之内|之前|之后|左右|内|前|后)?'
    r'|(?:今年|明年|去年|前年|后年|本月|上个月|下个月|上月|下月|本周|上周|下周|本週|上週|下週|本季度|上季度|下季度|今天|昨天|明天|近期|短期|中期|长期|長期)'
)
AMOUNT=re.compile(rf'(?:{NUMBER}(?:[十百千万萬亿億兆]+)?(?:美金|美元|欧元|歐元|人民币|人民幣|卢比|盧比|日元|港元|港币|港幣|英镑|英鎊|元|%|％)|百分之{NUMBER})')


def time_quotes(segments):
    # Removing whitespace supports a phrase split across adjacent ASR fragments.
    # Exact-field validation still checks the selected claim's own source range.
    text=re.sub(r'\s+','',''.join(s['text'] for s in segments))
    return list(dict.fromkeys(match.group(0) for match in TIME.finditer(text)))


def amount_only(text):
    return bool(AMOUNT.fullmatch(re.sub(r'[\s,，]','',text)))
