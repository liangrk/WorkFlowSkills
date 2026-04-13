#!/usr/bin/env python3
"""Parse UI hierarchy XML and generate interactive HTML tree view."""

import xml.etree.ElementTree as ET
import sys
from pathlib import Path


def parse_xml(xml_file):
    try:
        return ET.parse(xml_file).getroot()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def gen_html(root, pkg='unknown'):
    stats = {'total': 0, 'clickable': 0, 'text': 0, 'id': 0, 'types': {}}
    def walk(n):
        stats['total'] += 1
        if n.get('clickable') == 'true': stats['clickable'] += 1
        if n.get('text'): stats['text'] += 1
        if n.get('resource-id'): stats['id'] += 1
        c = n.get('class', 'unknown').split('.')[-1]
        stats['types'][c] = stats['types'].get(c, 0) + 1
        for ch in n: walk(ch)
    walk(root)

    def render(n, d=0):
        h = []
        cls = n.get('class', 'unknown').split('.')[-1]
        rid = n.get('resource-id', '')
        txt = n.get('text', '')
        desc = n.get('content-desc', '')
        click = n.get('clickable', 'false') == 'true'
        bounds = n.get('bounds', '')
        kids = list(n)

        h.append('<div class="n" style="margin-left:%dpx" onclick="hl(this)">' % (d*20))
        if kids: h.append('<span class="b" onclick="tg(this)">▼</span>')
        else: h.append('<span style="color:#ccc;margin-right:5px">•</span>')
        h.append('<span class="t">%s</span>' % cls)
        if rid: h.append(' <span class="i" onclick="cp(\'%s\')" title="%s">[%s]</span>' % (rid, rid, rid.split('/')[-1]))
        if txt:
            t = txt[:50] + ("..." if len(txt)>50 else "")
            h.append(' <span class="x">"%s"</span>' % t)
        if desc: h.append(' <span style="color:#888">📝%s</span>' % desc)
        if click: h.append(' <span style="background:#0078d4;color:#fff;padding:1px 6px;border-radius:3px;font-size:.8em">CLICK</span>')
        if bounds: h.append(' <span style="color:#888;font-size:.85em">📐%s</span>' % bounds)
        h.append('</div>')
        if kids:
            h.append('<div class="c">')
            for k in kids: h.append(render(k, d+1))
            h.append('</div>')
        return ''.join(h)

    types_html = ''.join('<tr><td>%s</td><td>%d</td><td>%.1f%%</td></tr>' % (k, v, v/stats["total"]*100)
                         for k,v in sorted(stats['types'].items(), key=lambda x:x[1], reverse=True))

    js = """<script>
function tg(btn){var p=btn.parentElement,t=p.querySelector(':scope>.c');if(t){t.style.display=t.style.display==='none'?'block':'none';btn.textContent=t.style.display==='none'?'▶':'▼'}}
function hl(e){document.querySelectorAll('.hl').forEach(function(x){x.classList.remove('hl')});e.classList.add('hl')}
function cp(t){navigator.clipboard.writeText(t);var tip=document.getElementById('tip');tip.textContent='Copied!';tip.style.display='block';setTimeout(function(){tip.style.display='none'},2000)}
function sq(q){q=q.toLowerCase();document.querySelectorAll('.n').forEach(function(n){n.style.display=n.textContent.toLowerCase().indexOf(q)!==-1?'block':'none'})}
</script>"""

    html = '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>UI Hierarchy - %s</title>' % pkg
    html += '<style>body{font-family:\'Segoe UI\',sans-serif;margin:20px;background:#f5f5f5}.s{background:#fff;padding:20px;margin:20px 0;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,.1);display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px}.sn{text-align:center}.num{font-size:2em;font-weight:700;color:#0078d4}.lbl{color:#666;font-size:.9em}.n{padding:6px 10px;margin:4px 0;background:#fafafa;border-left:3px solid #0078d4;border-radius:4px;cursor:pointer}.n:hover{background:#e8f4ff}.n.hl{background:#fff4ce;border-left-color:#ffb900}.t{color:#0078d4;font-weight:700}.i{color:#107c10;cursor:pointer}.x{color:#d83b01;font-style:italic}.b{cursor:pointer;color:#666;margin-right:5px}table{width:100%%;border-collapse:collapse;background:#fff;padding:20px;border-radius:8px}th,td{padding:8px 12px;text-align:left;border-bottom:1px solid #eee}th{background:#f5f5f5}input{width:100%%;padding:8px;margin:15px 0;border:1px solid #ddd;border-radius:4px}#tip{display:none;position:fixed;top:20px;right:20px;background:#107c10;color:#fff;padding:8px 12px;border-radius:4px}</style>'
    html += js + '</head><body>'
    html += '<h1>📱 UI Hierarchy - %s</h1>' % pkg
    html += '<div class="s"><div class="sn"><div class="num">%d</div><div class="lbl">Views</div></div>' % stats['total']
    html += '<div class="sn"><div class="num">%d</div><div class="lbl">Clickable</div></div>' % stats['clickable']
    html += '<div class="sn"><div class="num">%d</div><div class="lbl">Text</div></div>' % stats['text']
    html += '<div class="sn"><div class="num">%d</div><div class="lbl">IDs</div></div></div>' % stats['id']
    html += '<input placeholder="Search..." onkeyup="sq(this.value)"><div id="tip"></div>'
    html += '<div style="background:#fff;padding:20px;border-radius:8px">%s</div>' % render(root)
    html += '<h2>View Types</h2><table><tr><th>Type</th><th>Count</th><th>%%</th></tr>%s</table>' % types_html
    html += '</body></html>'
    return html


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_ui_xml.py <input.xml> [output.html]")
        sys.exit(1)
    root = parse_xml(sys.argv[1])
    if not root: sys.exit(1)
    out = sys.argv[2] if len(sys.argv) > 2 else 'tree_view.html'
    pkg = root.get('package', 'unknown')
    Path(out).write_text(gen_html(root, pkg), encoding='utf-8')
    print("Generated: %s" % out)


if __name__ == '__main__':
    main()
