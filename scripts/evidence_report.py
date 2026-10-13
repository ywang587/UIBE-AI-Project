"""Validate an analysis against ASR evidence and render a local reading report.

This does not call a language model. Supply an explicitly labelled analysis JSON.
"""
import argparse
import html
import json
from pathlib import Path
from transcribe import sha256


def validate(transcript, analysis):
    if analysis['source_sha256'] != transcript['source']['sha256']:
        raise ValueError('分析与转录来源不一致')
    if not analysis.get('method') or not analysis.get('claims'):
        raise ValueError('必须注明分析方式并提供主张')
    evidence = {s['id']: s for s in transcript['segments']}
    for claim in analysis['claims']:
        if claim['kind'] not in {'博主事实性主张', '博主解释', '博主评价', '博主预测', '推广'}:
            raise ValueError('无效的主张类别')
        if not claim.get('statement') or not claim.get('evidence'):
            raise ValueError('主张缺少文字或原文依据')
        for citation in claim['evidence']:
            segment = evidence[citation['segment_id']]
            if not citation.get('quote') or citation['quote'] not in segment['text']:
                raise ValueError('引文不在所引原文片段中')
    return evidence


def render(transcript, analysis, video, output):
    evidence = validate(transcript, analysis)
    if sha256(video) != analysis['source_sha256']:
        raise ValueError('视频与分析来源不一致')
    esc = html.escape
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    for claim in analysis['claims']:
        quotes = []
        for c in claim['evidence']:
            s = evidence[c['segment_id']]
            quotes.append(f'<button data-time="{s["start"]}">{s["start"]:.1f}–{s["end"]:.1f} 秒</button> {esc(c["quote"])}')
        blocks.append(f'<article><small>{esc(claim["kind"])}</small><h2>{esc(claim["statement"])}</h2><blockquote>{"<br>".join(quotes)}</blockquote><p class="note">{esc(claim.get("limitation", "尚未外部核实"))}</p></article>')
    rows = ''.join(f'<p><button data-time="{s["start"]}">{s["start"]:.1f} 秒</button> {esc(s["text"])}</p>' for s in transcript['segments'])
    caveats = ''.join(f'<li>{esc(x)}</li>' for x in analysis.get('limitations', []))
    result = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>视频解读与原文证据</title>
<style>body{margin:0;background:#f3f5f8;color:#192c3e;font:16px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:1180px;margin:36px auto;padding:0 24px}h1{font-size:30px;margin:10px 0}h2{font-size:19px;margin:8px 0}small{color:#216b77}article,.panel{background:white;padding:22px 26px;border-radius:14px;margin-bottom:18px;border:1px solid #e0e5ec}blockquote{margin:12px 0;padding:12px 16px;border-left:3px solid #78acb4;background:#f1f7f7}button{cursor:pointer;border:0;border-radius:6px;background:#d9ecee;color:#21575d;padding:5px 9px;margin:3px 8px 3px 0}.note{color:#687484;font-size:14px}.grid{display:grid;grid-template-columns:330px 1fr;gap:24px}video{width:100%;max-height:550px;background:#111;border-radius:10px}li{margin-bottom:7px}@media(max-width:800px){.grid{display:block}}</style><main>
'''
    result += f'<small>UIBE AI · 单条视频证据样例</small><h1>{esc(analysis["title"])}</h1><p>{esc(analysis["method"])}</p><div class="grid"><aside><video id="video" controls preload="metadata" src="{esc(Path(video).resolve().as_uri(), quote=True)}"></video><p class="note">点击时间跳转原视频。原稿保留识别错误；事实性主张未自动视为已核实事实。</p><div class="panel"><h2>尚不能判断</h2><ul>{caveats}</ul></div></aside><section>{"".join(blocks)}<div class="panel"><h2>外部背景与核查</h2><p>本样例尚未加入外部核查。事件具体日期不明，不把当前数据套用到视频所述时期。</p><h2>跨博主对照</h2><p>暂未建立同一事件的可比较样本，不自动生成共识或分歧。</p></div><details class="panel"><summary>查看完整时间戳文字稿</summary>{rows}</details></section></div></main>'
    result += '<script>document.querySelectorAll("button[data-time]").forEach(b=>b.addEventListener("click",()=>{const v=document.getElementById("video");v.currentTime=Number(b.dataset.time);v.play().catch(()=>{});}));</script></html>'
    output.write_text(result, encoding='utf-8')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('transcript', type=Path)
    p.add_argument('analysis', type=Path)
    p.add_argument('video', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    render(json.loads(a.transcript.read_text(encoding='utf-8')), json.loads(a.analysis.read_text(encoding='utf-8')), a.video, a.output)
