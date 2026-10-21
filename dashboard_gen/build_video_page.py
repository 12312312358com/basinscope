# -*- coding: utf-8 -*-
"""把 video_data.json 渲染成自包含的 `video_analysis.html`（内联 ECharts + 缩略图）。

不依赖网络：ECharts 取自项目本地 static/js/echarts.min.js，缩略图内联 base64。
"""
import base64
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, '..'))
DATA = os.path.join(_HERE, 'video_data.json')
ECHARTS = os.path.join(REPO, 'static', 'js', 'echarts.min.js')
VF = os.path.join(REPO, 'video_features')
OUT = os.path.join(_HERE, 'video_analysis.html')

_HUE_COLOR = {'红': '#e05252', '橙': '#e08a3c', '黄': '#d8c53a', '绿': '#4caf78',
              '青': '#3fb0b0', '蓝': '#4a83d4', '紫': '#8a6fd0', '品红': '#c4569b', '黑': '#666'}


def _thumb_b64(rel, max_w=420, q=78):
    """缩略图降采样后内嵌（原图 ~250KB/张，页面会到 8MB；降采样后 ~30KB）。"""
    p = os.path.join(VF, rel)
    if not os.path.exists(p):
        return None
    try:
        import io

        from PIL import Image
        im = Image.open(p).convert('RGB')
        if im.width > max_w:
            im = im.resize((max_w, max(1, int(im.height * max_w / im.width))))
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=q)
        raw = buf.getvalue()
    except Exception:
        with open(p, 'rb') as f:
            raw = f.read()
    return 'data:image/jpeg;base64,' + base64.b64encode(raw).decode()


def build():
    d = json.load(open(DATA, encoding='utf-8'))
    echarts_js = open(ECHARTS, encoding='utf-8').read()

    cards = []
    for t in d['l2']['thumbs']:
        b64 = _thumb_b64(t['sheet'])
        if not b64:
            continue
        cards.append(
            '<figure class="thumb"><img src="%s" loading="lazy">'
            '<figcaption>%s · %s/%s · %ss · %s</figcaption></figure>'
            % (b64, t['id'], t.get('basin') or '-', t.get('topic') or '-', t.get('dur'), t.get('hue')))

    meta = d['meta']
    html = _TPL % {
        'echarts': echarts_js,
        'data': json.dumps(d, ensure_ascii=False),
        'hue_color': json.dumps(_HUE_COLOR, ensure_ascii=False),
        'cards': '\n'.join(cards),
        'l1n': meta['l1_n'], 'l2n': meta['l2_n'], 'l2ok': meta['l2_ok'], 'l3n': meta['l3_n'],
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print('[video_page] 写出 %s (%.1f MB)' % (OUT, os.path.getsize(OUT) / 1024 / 1024))
    return OUT


_TPL = r"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>视频分析总览 · BasinScope</title>
<style>
:root{--bg:#12161c;--card:#1b2029;--line:#2a3240;--fg:#e8edf4;--sub:#9aa7b8;--acc:#5aa9ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 system-ui,"Microsoft YaHei",sans-serif}
header{padding:20px 26px;border-bottom:1px solid var(--line)}
h1{margin:0;font-size:20px;font-weight:600}
header .sub{color:var(--sub);font-size:13px;margin-top:4px}
.kpis{display:flex;gap:12px;flex-wrap:wrap;padding:16px 26px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 18px;min-width:130px}
.kpi b{display:block;font-size:24px;color:var(--acc)}
.kpi span{color:var(--sub);font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px;padding:6px 26px 24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.card h3{margin:2px 0 6px;font-size:14px;font-weight:600;color:#cdd8e6}
.card h3 small{color:var(--sub);font-weight:400;font-size:11px;margin-left:6px}
.chart{height:230px}
h2.sec{padding:10px 26px 0;font-size:16px;color:#cdd8e6;border-top:1px solid var(--line);margin-top:8px}
.wall{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px;padding:6px 26px 30px}
.thumb{margin:0;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.thumb img{width:100%%;display:block}
.thumb figcaption{padding:6px 9px;color:var(--sub);font-size:11px}
.note{padding:8px 26px 30px;color:var(--sub);font-size:12px}
</style></head><body>
<header>
  <h1>视频分析总览 · 舆情短视频三层特征</h1>
  <div class="sub">L1 元数据/封面/评论（全量） · L2 关键帧（抽样） · L3 音频（待装 ASR 后端）　|　数字均来自真实统计，无估值</div>
</header>
<div class="kpis">
  <div class="kpi"><b>%(l1n)s</b><span>L1 内容条数</span></div>
  <div class="kpi"><b>%(l2n)s</b><span>L2 抽样条数</span></div>
  <div class="kpi"><b>%(l2ok)s</b><span>L2 成功抽帧</span></div>
  <div class="kpi"><b>%(l3n)s</b><span>L3 音频条数</span></div>
</div>

<h2 class="sec">L1 · 元数据 / 封面 / 评论</h2>
<div class="grid">
  <div class="card"><h3>平台分布</h3><div class="chart" id="c_plat"></div></div>
  <div class="card"><h3>流域分布<small>含未标/非流域</small></h3><div class="chart" id="c_basin"></div></div>
  <div class="card"><h3>议题分布</h3><div class="chart" id="c_topic"></div></div>
  <div class="card"><h3>互动总量分布</h3><div class="chart" id="c_inter"></div></div>
  <div class="card"><h3>封面主色调<small>708 条有封面</small></h3><div class="chart" id="c_hue"></div></div>
  <div class="card"><h3>封面亮度</h3><div class="chart" id="c_bright"></div></div>
  <div class="card"><h3>评论情感<small>1028 条有评论</small></h3><div class="chart" id="c_sent"></div></div>
  <div class="card"><h3>评论诉求</h3><div class="chart" id="c_demand"></div></div>
</div>

<h2 class="sec">L2 · 关键帧画面</h2>
<div class="grid">
  <div class="card"><h3>抽帧数分布</h3><div class="chart" id="c_frames"></div></div>
  <div class="card"><h3>时长分布</h3><div class="chart" id="c_dur2"></div></div>
  <div class="card"><h3>画面主色调</h3><div class="chart" id="c_hue2"></div></div>
  <div class="card"><h3>画幅（横/竖屏）</h3><div class="chart" id="c_orient"></div></div>
</div>
<div class="wall">%(cards)s</div>
<div class="note">缩略图 = 该条抽到的关键帧拼图（按全片均匀采样，修复后覆盖全片）。取自 L2 抽样的 110 条有效内容。</div>

<script>%(echarts)s</script>
<script>
var D=%(data)s, HC=%(hue_color)s;
function bar(id,arr,color,horiz){var el=document.getElementById(id);if(!el)return;
 var names=arr.map(function(x){return x.name}), vals=arr.map(function(x){return x.value});
 var opt={grid:{left:horiz?90:40,right:16,top:12,bottom:24},tooltip:{trigger:'axis'},
  xAxis:horiz?{type:'value',axisLabel:{color:'#9aa7b8'}}:{type:'category',data:names,axisLabel:{color:'#9aa7b8',interval:0,rotate:names.length>5?30:0}},
  yAxis:horiz?{type:'category',data:names,axisLabel:{color:'#9aa7b8'}}:{type:'value',axisLabel:{color:'#9aa7b8'}},
  series:[{type:'bar',data:vals,itemStyle:{color:color||'#5aa9ff',borderRadius:3},
    label:{show:true,position:horiz?'right':'top',color:'#cdd8e6',fontSize:10}}]};
 if(horiz){var t=opt.xAxis;opt.xAxis=opt.yAxis;opt.yAxis=t;}
 echarts.init(el).setOption(opt);}
function pie(id,arr){var el=document.getElementById(id);if(!el)return;
 echarts.init(el).setOption({tooltip:{trigger:'item'},legend:{bottom:0,textStyle:{color:'#9aa7b8'}},
  series:[{type:'pie',radius:['42%%','68%%'],label:{color:'#cdd8e6'},data:arr}]});}
function hueBar(id,arr){var el=document.getElementById(id);if(!el)return;
 echarts.init(el).setOption({grid:{left:40,right:16,top:12,bottom:24},tooltip:{},
  xAxis:{type:'category',data:arr.map(function(x){return x.name}),axisLabel:{color:'#9aa7b8'}},
  yAxis:{type:'value',axisLabel:{color:'#9aa7b8'}},
  series:[{type:'bar',data:arr.map(function(x){return {value:x.value,itemStyle:{color:HC[x.name]||'#5aa9ff'}}})}]});}

pie('c_plat',D.l1.platform); bar('c_basin',D.l1.basin,'#4caf78'); pie('c_topic',D.l1.topic);
bar('c_inter',D.l1.interact.buckets,'#e08a3c'); hueBar('c_hue',D.l1.cover.hue);
bar('c_bright',D.l1.cover.bright,'#d8c53a'); pie('c_sent',D.l1.comment.sentiment);
bar('c_demand',D.l1.comment.demand,'#5aa9ff',true);
bar('c_frames',D.l2.frames.buckets,'#5aa9ff'); bar('c_dur2',D.l2.duration,'#4caf78');
hueBar('c_hue2',D.l2.hue); pie('c_orient',D.l2.orient);
</script></body></html>
"""


if __name__ == '__main__':
    build()
