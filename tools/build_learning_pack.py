#!/usr/bin/env python3
"""Build the portable CareJiyo library and printable manuals from shipped content.

Usage: python tools/build_learning_pack.py OUTPUT --media /path/to/private/media
The output is a client handover; keep it in a private, authorised location.
"""
import argparse
import html
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ["Getting started and enquiries", "Bookings and operations", "Mobile visits",
            "Invoices and payments", "Users and administration", "Worked examples"]
STYLE = """
:root{font-family:Arial,sans-serif;color:#19394a;background:#f5f8fa;font-size:16px;line-height:1.65}
*{box-sizing:border-box}body{margin:0}header{background:#163d4b;color:white;padding:32px 5vw}header a{color:#bde8dc}h1,h2{line-height:1.25}main{max-width:1180px;margin:auto;padding:30px 24px}a{color:#08786e}button,input,select{font:inherit;padding:10px 14px;border:1px solid #b8cbd0;border-radius:8px;background:white;color:#19394a}button{cursor:pointer}button:focus-visible,a:focus-visible{outline:3px solid #c68b3c}nav{display:flex;flex-wrap:wrap;gap:14px}.filters{display:grid;grid-template-columns:2fr 1fr;gap:16px;margin:24px 0}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px}article,.paper{background:white;border:1px solid #d4e1e5;border-radius:10px;padding:24px;margin:0 0 24px}article h2{font-size:22px;margin-top:4px}.small{font-size:14px;color:#536b78}li{margin-bottom:14px}aside{border-left:4px solid #c68b3c;padding:12px 16px;background:#fff7ea}video{width:100%;max-height:70vh;background:#163d4b}video::cue{font-size:16px;background:rgba(15,40,48,.88);color:#fff}#chapters{display:flex;flex-wrap:wrap;gap:8px;margin:15px 0}#chapters button{font-size:14px;text-align:left}.toc{columns:2}.paper{max-width:950px;margin:0 auto 24px}footer{padding:24px;text-align:center}.actions{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}[hidden]{display:none!important}
@media(max-width:650px){.filters{grid-template-columns:1fr}.toc{columns:1}main{padding:20px 14px}}
@media print{header{background:white;color:#19394a;padding:0}body{background:white}main{padding:0;max-width:none}button,.no-print{display:none!important}.paper{border:0;padding:0;break-before:page}li{break-inside:avoid}h2,h3{break-after:avoid}a{color:inherit}footer{font-size:12px}}@page{size:A4;margin:18mm}
"""


def shell(title, body, extra=''):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>'+html.escape(title)+'</title><style>'+STYLE+'</style></head><body>'+body+extra+'</body></html>')


def topic(t):
    e = html.escape
    return ('<article class="paper" id="'+e(t['key'])+'"><h2>'+e(t['title'])+'</h2><p>'+e(t['goal'])+
            '</p><p><b>Who uses this:</b> '+e(t['role'])+'</p><h3>Before you begin</h3><p>'+e(t['before'])+'</p>'+
            ('<aside>'+e(t['warning'])+'</aside>' if t['warning'] else '')+
            '<h3>Steps</h3><ol>'+''.join('<li>'+e(s)+'</li>' for s in t['steps'])+'</ol>'+
            '<h3>Check the result</h3><p>'+e(t['success'])+'</p><h3>If something is wrong</h3><p>'+e(t['trouble'])+'</p>'+
            '<p class="no-print"><a href="../index.html#'+e(t['key'])+'">Open this task in the learning library</a></p></article>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--media', type=Path)
    args = parser.parse_args()
    data = json.loads((ROOT/'addons/health_learn/data/learning_catalog.json').read_text())
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT/'addons/health_learn/static/src/library/poster.svg', out/'poster.svg')
    (out/'manuals').mkdir(parents=True, exist_ok=True)
    (out/'media/captions').mkdir(parents=True, exist_ok=True)
    for t in data['tasks']:
        t['video'] = bool(args.media and t.get('media') and (args.media/(t['media']+'.mp4')).is_file())
        if t['video']:
            shutil.copy2(args.media/(t['media']+'.mp4'), out/'media'/(t['key']+'.mp4'))
            t['captions'] = {}
            for lang in ('en','vi'):
                source = args.media/(t['media']+'.'+lang+'.vtt')
                shutil.copy2(source, out/'media/captions'/(t['key']+'.'+lang+'.vtt'))
                # Blob tracks also work when index.html is opened directly from disk.
                t['captions'][lang] = source.read_text()
        t.pop('media', None)
    intro = '<p>Use your own staff account at <a href="https://carejiox.com">carejiox.com</a>. Follow the guide for your role and assigned catchment. Before saving, confirm the client and booking reference. The worked examples illustrate calculations; use the current approved clinic tariff for actual work.</p>'
    links = []
    for number, name in enumerate(SECTIONS, 1):
        filename = f'{number:02}-'+name.lower().replace(' ','-')+'.html'
        links.append('<a href="manuals/'+filename+'">'+html.escape(name)+'</a>')
        tasks = [t for t in data['tasks'] if t['section'] == number]
        write_manual(out/'manuals'/filename, 'CareJiyo user manual · '+name, tasks, intro)
    write_manual(out/'manuals/complete-manual.html', 'CareJiyo user manual', data['tasks'], intro)
    quick = '<header><h1>CareJiyo quick reference</h1><a href="../index.html">Learning library</a></header><main>'+intro
    for role, keys in data['paths'].items():
        quick += '<article><h2>'+html.escape({'crm':'CRM','clinical':'Nurse or doctor','owner':'Owner','operations':'Operations Manager','finance':'Finance'}[role])+'</h2><ol>'
        for key in keys:
            t = next(t for t in data['tasks'] if t['key'] == key)
            quick += '<li><a href="complete-manual.html#'+key+'">'+html.escape(t['title'])+'</a> — '+html.escape(t['success'])+'</li>'
        quick += '</ol></article>'
    (out/'manuals/quick-reference.html').write_text(shell('CareJiyo quick reference',quick+'</main><footer>CareJiyo user manual</footer>'))
    body = '<header><h1>CareJiyo Learning</h1><p>Find your task. Watch the walkthrough. Follow the steps.</p><nav><a href="https://carejiox.com">Open CareJiyo</a><a href="manuals/complete-manual.html">Complete user manual</a><a href="manuals/quick-reference.html">Quick reference</a></nav></header><main><section id="browse"><h2>Learn at your own pace</h2><p>In the application, open <b>Learn → Task guides and videos</b> for role learning paths and saved progress. Open <b>Care Coach → Guides and videos</b> for help beside your current screen.</p><nav>'+''.join(links)+'</nav><div class="filters"><input id="search" type="search" aria-label="Search tasks" placeholder="Search a task in English or Vietnamese"><select id="section" aria-label="Topic area"><option value="">All topics</option>'+''.join('<option value="'+str(i)+'">'+s+'</option>' for i,s in enumerate(SECTIONS,1))+'</select></div><div id="cards" class="grid"></div></section><section id="detail" hidden><button id="back">Back to topics</button><h2 id="title"></h2><p id="goal"></p><div id="player" hidden><video id="video" poster="poster.svg" controls playsinline preload="metadata"></video><p class="small">Choose English or Vietnamese subtitles in the video controls.</p><div id="chapters"></div></div><div id="guide"></div></section></main><footer>CareJiyo Learning</footer>'
    script = r'''
const tasks=DATA.tasks, byId=Object.fromEntries(tasks.map(t=>[t.key,t]));
const $=id=>document.getElementById(id);
function el(tag,text,parent){const n=document.createElement(tag);if(text)n.textContent=text;if(parent)parent.append(n);return n;}
function render(){const q=$('search').value.toLowerCase(),section=$('section').value;$('cards').replaceChildren();for(const t of tasks.filter(t=>(!section||String(t.section)===section)&&(!q||[t.title,t.title_vi,t.goal,...t.search_phrases].join(' ').toLowerCase().includes(q)))){const a=el('article','',$('cards'));el('h2',t.title,a);el('p',t.goal,a);const b=el('button',t.video?'Read guide / watch video':'Read guide',a);b.onclick=()=>location.hash=t.key;}}
let urls=[];
function open(){const key=decodeURIComponent(location.hash.slice(1)),t=byId[key];$('video').pause();urls.forEach(URL.revokeObjectURL);urls=[];$('browse').hidden=!!t;$('detail').hidden=!t;if(!t)return;window.scrollTo(0,0);$('title').textContent=t.title;$('goal').textContent=t.goal;$('player').hidden=!t.video;$('video').replaceChildren();$('video').removeAttribute('src');$('chapters').replaceChildren();if(t.video){$('video').src='media/'+t.key+'.mp4';for(const lang of ['en','vi']){const tr=el('track','',$('video'));tr.kind='subtitles';tr.srclang=lang;tr.label=lang==='en'?'English':'Tiếng Việt';tr.default=lang==='en';const url=URL.createObjectURL(new Blob([t.captions[lang]],{type:'text/vtt'}));urls.push(url);tr.src=url;}for(const c of t.chapters){const b=el('button',Math.floor(c.start/60)+':'+String(Math.floor(c.start%60)).padStart(2,'0')+' · '+c.title,$('chapters'));b.onclick=()=>{$('video').currentTime=c.start;$('video').scrollIntoView({block:'center',behavior:'smooth'});$('video').play();};}}$('guide').replaceChildren();const a=el('article','',$('guide'));el('h3','Before you begin',a);el('p',t.before,a);if(t.warning)el('aside',t.warning,a);el('h3','Steps',a);const ol=el('ol','',a);t.steps.forEach(s=>el('li',s,ol));el('h3','Check the result',a);el('p',t.success,a);el('h3','If something is wrong',a);el('p',t.trouble,a);const link=el('a','Open printable guide',a);link.href='manuals/complete-manual.html#'+t.key;}
$('search').oninput=render;$('section').onchange=render;$('back').onclick=()=>location.hash='';window.addEventListener('hashchange',open);render();open();
'''
    (out/'content.js').write_text('const DATA='+json.dumps(data,ensure_ascii=False).replace('</','<\\/')+';\n')
    (out/'library.js').write_text(script)
    (out/'index.html').write_text(shell('CareJiyo Learning',body,'<script src="content.js"></script><script src="library.js"></script>'))
    (out/'Read me.txt').write_text('CAREJIYO LEARNING\n\nOpen index.html in Chrome. Keep the media folder with this file. Subtitles are in media/captions; the library loads them automatically.\n\nManuals: open a volume or the complete manual, then Print / Save as PDF.\n\nUse Learn > Task guides and videos inside CareJiyo for saved progress, role pathways and Ask the coach. In-app videos require your staff login.\n\nInstructions are in English. Topic titles and video subtitles also support Vietnamese.\n')
    print(f'Built {len(data["tasks"])} topics, {sum(t["video"] for t in data["tasks"])} videos and 8 manuals at {out}')


def write_manual(path, title, tasks, intro):
    toc='<nav class="toc"><ul>'+''.join('<li><a href="#'+t['key']+'">'+html.escape(t['title'])+'</a></li>' for t in tasks)+'</ul></nav>'
    body='<header><h1>'+html.escape(title)+'</h1><nav class="no-print"><a href="../index.html">Learning library</a><button onclick="window.print()">Print or save as PDF</button></nav></header><main>'+intro+toc+''.join(topic(t) for t in tasks)+'</main><footer>CareJiyo user manual</footer>'
    path.write_text(shell(title,body))


if __name__=='__main__':main()
