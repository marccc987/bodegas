"""Build single-page interactive dashboard with embedded data."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlmodel import Session, select
from bodegas.db.session import get_engine
from bodegas.db.models import Account, Relationship

engine = get_engine()
with Session(engine) as s:
    accs = s.exec(select(Account)).all()
    rels = s.exec(select(Relationship)).all()

accounts_data = []
for a in accs:
    accounts_data.append({
        'id': a.id, 'u': a.username, 'dn': a.display_name or '',
        'av': a.avatar_url or '', 'fl': a.followers_count or 0,
        'fg': a.following_count or 0, 'tc': a.tweet_count or 0,
        'bl': a.bot_label or '', 'bs': round(a.bot_score or 0, 3),
        'ci': a.community_id, 'seed': a.is_seed or False,
        'bio': a.has_bio or False, 'hav': a.has_avatar or False,
    })

edges_data = []
for r in rels:
    edges_data.append({
        's': r.source_id, 't': r.target_id,
        'tp': r.relationship_type, 'w': r.weight or 1,
    })

data_json = json.dumps({'accounts': accounts_data, 'edges': edges_data})

# Inline vis-network.js for Streamlit iframe compatibility
vis_js_path = Path("/tmp/vis-network.min.js")
if not vis_js_path.exists():
    import urllib.request
    urllib.request.urlretrieve(
        "https://unpkg.com/vis-network@9.1.2/standalone/umd/vis-network.min.js",
        str(vis_js_path),
    )
vis_js_inline = vis_js_path.read_text(encoding="utf-8")

# Stats
total = len(accounts_data)
synced = [a for a in accounts_data if a['tc'] == 34]
bots = [a for a in accounts_data if a['bl'] == 'bot']
suspicious = [a for a in accounts_data if a['bl'] == 'suspicious']
seeds = [a for a in accounts_data if a['seed']]
communities = set(a['ci'] for a in accounts_data if a['ci'] is not None)

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bodegas - Analisis de Red y Deteccion de Cuentas Coordinadas</title>
<script>{vis_js_inline}</script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background:#0a0a14; color:#e0e0e0; }}
.header {{ background:linear-gradient(135deg, #0f0f2a 0%, #1a0a2e 100%); padding:24px 32px; border-bottom:1px solid #2a2a4a; }}
.header h1 {{ font-size:22px; color:#fff; margin-bottom:4px; }}
.header p {{ font-size:13px; color:#888; }}
.stats {{ display:flex; gap:12px; padding:16px 32px; flex-wrap:wrap; }}
.stat {{ background:#12122a; border:1px solid #2a2a4a; border-radius:10px; padding:14px 20px; min-width:140px; flex:1; }}
.stat .val {{ font-size:28px; font-weight:700; color:#fff; }}
.stat .lbl {{ font-size:11px; color:#888; text-transform:uppercase; letter-spacing:1px; margin-top:2px; }}
.stat.alert .val {{ color:#e74c3c; }}
.stat.warn .val {{ color:#f39c12; }}
.stat.ok .val {{ color:#2ecc71; }}
.tabs {{ display:flex; gap:0; border-bottom:1px solid #2a2a4a; padding:0 32px; background:#0d0d1f; }}
.tab {{ padding:12px 24px; cursor:pointer; color:#888; font-size:14px; border-bottom:2px solid transparent; transition:all .2s; }}
.tab:hover {{ color:#fff; }}
.tab.active {{ color:#fff; border-bottom-color:#6c5ce7; }}
.panel {{ display:none; padding:20px 32px; }}
.panel.active {{ display:block; }}
#graph {{ width:100%; height:600px; border:1px solid #2a2a4a; border-radius:10px; background:#0a0a14; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:#1a1a3a; padding:10px 12px; text-align:left; font-weight:600; color:#aaa; text-transform:uppercase; font-size:11px; letter-spacing:.5px; position:sticky; top:0; }}
td {{ padding:8px 12px; border-bottom:1px solid #1a1a2a; }}
tr:hover td {{ background:#15152a; }}
.avatar {{ width:28px; height:28px; border-radius:50%; vertical-align:middle; margin-right:6px; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; }}
.badge.bot {{ background:#e74c3c33; color:#e74c3c; }}
.badge.suspicious {{ background:#f39c1233; color:#f39c12; }}
.badge.human {{ background:#2ecc7133; color:#2ecc71; }}
.badge.synced {{ background:#9b59b633; color:#9b59b6; }}
.sync-card {{ background:linear-gradient(135deg, #1a0a2e, #2a1040); border:1px solid #6c5ce744; border-radius:12px; padding:20px; margin-bottom:16px; }}
.sync-card h3 {{ color:#e74c3c; margin-bottom:8px; }}
.sync-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(200px, 1fr)); gap:8px; margin-top:12px; }}
.sync-item {{ background:#0a0a1a; border:1px solid #2a2a4a; border-radius:8px; padding:10px; display:flex; align-items:center; gap:8px; }}
.sync-item img {{ width:32px; height:32px; border-radius:50%; border:2px solid #e74c3c; }}
.sync-item .noav {{ width:32px; height:32px; border-radius:50%; background:#e74c3c33; border:2px solid #e74c3c; display:flex; align-items:center; justify-content:center; font-size:14px; }}
.sync-item span {{ font-size:12px; }}
.filter-row {{ display:flex; gap:12px; margin-bottom:16px; flex-wrap:wrap; align-items:center; }}
.filter-row input, .filter-row select {{ background:#12122a; border:1px solid #2a2a4a; color:#e0e0e0; padding:8px 12px; border-radius:6px; font-size:13px; }}
.filter-row input {{ min-width:200px; }}
.legend {{ display:flex; gap:16px; flex-wrap:wrap; margin:12px 0; font-size:12px; }}
.legend-item {{ display:flex; align-items:center; gap:5px; }}
.legend-dot {{ width:12px; height:12px; border-radius:50%; }}
.community-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:12px; }}
.comm-card {{ background:#12122a; border:1px solid #2a2a4a; border-radius:10px; padding:16px; }}
.comm-card h4 {{ color:#6c5ce7; margin-bottom:8px; }}
.scroll-table {{ max-height:500px; overflow-y:auto; border-radius:10px; border:1px solid #2a2a4a; }}
a {{ color:#6c5ce7; text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
.methodology {{ background:#12122a; border:1px solid #2a2a4a; border-radius:10px; padding:20px; margin-top:16px; line-height:1.7; }}
.methodology h3 {{ color:#fff; margin-bottom:10px; }}
.methodology ul {{ padding-left:20px; margin:8px 0; }}
.methodology li {{ margin:4px 0; }}
</style>
</head>
<body>
<div class="header">
  <h1>Bodegas - Red de Cuentas Coordinadas en X</h1>
  <p>Analisis de la campaña presidencial 2026 en Colombia &middot; {total} cuentas &middot; {len(edges_data)} relaciones &middot; Ultima actualizacion: 25 mar 2026</p>
</div>

<div class="stats">
  <div class="stat"><div class="val">{total}</div><div class="lbl">Cuentas</div></div>
  <div class="stat"><div class="val">{len(edges_data)}</div><div class="lbl">Relaciones</div></div>
  <div class="stat alert"><div class="val">{len(synced)}</div><div class="lbl">Patron sincronizado</div></div>
  <div class="stat warn"><div class="val">{len(suspicious)}</div><div class="lbl">Sospechosas</div></div>
  <div class="stat ok"><div class="val">{len(communities)}</div><div class="lbl">Comunidades</div></div>
</div>

<div class="tabs">
  <div class="tab active" onclick="showTab('graph')">Grafo de Red</div>
  <div class="tab" onclick="showTab('sync')">Patron Sincronizado</div>
  <div class="tab" onclick="showTab('accounts')">Cuentas</div>
  <div class="tab" onclick="showTab('communities')">Comunidades</div>
  <div class="tab" onclick="showTab('methodology')">Metodologia</div>
</div>

<div id="panel-graph" class="panel active">
  <div class="legend">
    <div class="legend-item"><div class="legend-dot" style="background:#e74c3c"></div> Bot</div>
    <div class="legend-item"><div class="legend-dot" style="background:#f39c12"></div> Sospechosa</div>
    <div class="legend-item"><div class="legend-dot" style="background:#2ecc71"></div> Humana</div>
    <div class="legend-item"><div class="legend-dot" style="background:#95a5a6"></div> Sin clasificar</div>
    <div class="legend-item"><div class="legend-dot" style="background:#9b59b6"></div> Patron 34 tweets</div>
    <span style="color:#666;margin-left:auto;font-size:11px;">Nodo grande = mayor influencia (PageRank) &middot; Aristas: <span style="color:#3498db">mencion</span> | <span style="color:#e74c3c">retweet</span> | <span style="color:#2ecc71">follows</span> | <span style="color:#f39c12">reply</span></span>
  </div>
  <div id="graph"></div>
</div>

<div id="panel-sync" class="panel">
  <div class="sync-card">
    <h3>33 cuentas con EXACTAMENTE 34 tweets cada una</h3>
    <p style="color:#ccc;margin-bottom:8px;">
      Estas cuentas muestran un patron de actividad identico: todas publicaron exactamente 34 tweets.
      La probabilidad de que 33 cuentas independientes publiquen exactamente la misma cantidad de tweets es estadisticamente insignificante.
      Esto indica una operacion coordinada (bodega) donde las cuentas son controladas por un mismo operador o herramienta automatizada.
    </p>
    <p style="color:#f39c12;font-size:13px;">
      <strong>Indicadores adicionales:</strong> 13 de las 33 cuentas tienen usernames con sufijos numericos largos generados automaticamente.
      La mayoria no tiene avatar ni biografia. Todas interactuan con las mismas cuentas de campaña.
    </p>
    <div class="sync-grid" id="sync-grid"></div>
  </div>
</div>

<div id="panel-accounts" class="panel">
  <div class="filter-row">
    <input type="text" id="search" placeholder="Buscar username..." oninput="filterTable()">
    <select id="label-filter" onchange="filterTable()">
      <option value="">Todas las clasificaciones</option>
      <option value="bot">Bot</option>
      <option value="suspicious">Sospechosa</option>
      <option value="human">Humana</option>
      <option value="synced">Patron 34</option>
    </select>
    <select id="sort-filter" onchange="filterTable()">
      <option value="bs">Bot score (mayor)</option>
      <option value="tc">Tweets (mayor)</option>
      <option value="fl">Seguidores (mayor)</option>
      <option value="u">Username (A-Z)</option>
    </select>
  </div>
  <div class="scroll-table">
    <table>
      <thead><tr>
        <th>Cuenta</th><th>Clasificacion</th><th>Bot Score</th><th>Tweets</th><th>Seguidores</th><th>Siguiendo</th><th>Comunidad</th><th>Semilla</th>
      </tr></thead>
      <tbody id="accounts-tbody"></tbody>
    </table>
  </div>
</div>

<div id="panel-communities" class="panel">
  <div class="community-grid" id="comm-grid"></div>
</div>

<div id="panel-methodology" class="panel">
  <div class="methodology">
    <h3>Metodologia</h3>
    <p>Este analisis fue realizado mediante las siguientes tecnicas:</p>
    <ul>
      <li><strong>Recoleccion de datos:</strong> Scraping de busquedas publicas en X (hashtags, menciones, respuestas a tweets) para recopilar cuentas e interacciones.</li>
      <li><strong>Grafo de relaciones:</strong> Construccion de un grafo dirigido donde los nodos son cuentas y las aristas representan interacciones (menciones, retweets, respuestas, follows).</li>
      <li><strong>Deteccion de comunidades:</strong> Algoritmo de Louvain para identificar clusters de cuentas densamente conectadas.</li>
      <li><strong>Deteccion heuristica de bots:</strong> Reglas basadas en: ausencia de avatar/bio, usernames con sufijos numericos largos, actividad extrema, concentracion de interacciones, y nombres de campaña.</li>
      <li><strong>Analisis de sincronizacion:</strong> Deteccion de cuentas con conteos de actividad identicos — un indicador fuerte de operacion coordinada.</li>
      <li><strong>PageRank:</strong> Calculo de influencia relativa dentro del grafo para dimensionar nodos.</li>
    </ul>
    <h3 style="margin-top:16px;">Codigo fuente</h3>
    <p>El codigo completo esta disponible en <a href="https://github.com/marccc987/bodegas" target="_blank">github.com/marccc987/bodegas</a></p>
    <h3 style="margin-top:16px;">Limitaciones</h3>
    <ul>
      <li>Los datos fueron recopilados de busquedas publicas; no representan la totalidad de la actividad.</li>
      <li>La clasificacion heuristica no es definitiva — requiere revision humana.</li>
      <li>El patron de 34 tweets es un indicador fuerte pero no prueba absoluta de automatizacion.</li>
    </ul>
  </div>
</div>

<script>
const DATA = {data_json};

function showTab(name) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelector(`.tab[onclick="showTab('${{name}}')"]`).classList.add('active');
  document.getElementById('panel-' + name).classList.add('active');
}}

// === GRAPH ===
function buildGraph() {{
  const COLORS = {{ bot:'#e74c3c', suspicious:'#f39c12', human:'#2ecc71', '':'#95a5a6' }};
  const EDGE_COLORS = {{ mention:'#3498db88', retweet:'#e74c3c88', follows:'#2ecc7188', reply:'#f39c1288', quote:'#9b59b688' }};

  // Build adjacency for PageRank approximation
  const inDeg = {{}};
  DATA.edges.forEach(e => {{ inDeg[e.t] = (inDeg[e.t]||0) + e.w; }});
  const maxIn = Math.max(...Object.values(inDeg), 1);

  const nodes = DATA.accounts.filter(a => {{
    return DATA.edges.some(e => e.s === a.id || e.t === a.id);
  }}).map(a => {{
    const pr = (inDeg[a.id] || 0) / maxIn;
    const size = 12 + pr * 45;
    const isSynced = a.tc === 34;
    let color = COLORS[a.bl] || COLORS[''];
    if (isSynced) color = '#9b59b6';

    const node = {{
      id: a.id,
      label: '@' + a.u,
      title: `<div style="font-family:Arial;padding:6px"><b>@${{a.u}}</b><br>${{a.dn}}<br><span style="color:${{color}}">${{(a.bl||'sin clasificar').toUpperCase()}}</span>${{isSynced?' (PATRON 34)':''}}<br>Score: ${{a.bs}}<br>Tweets: ${{a.tc.toLocaleString()}}<br>Seguidores: ${{a.fl.toLocaleString()}}<br>Siguiendo: ${{a.fg.toLocaleString()}}<br>Comunidad: ${{a.ci}}</div>`,
      size: size,
      font: {{ size: Math.max(8, 7 + pr*8), color: '#e0e0e0' }},
    }};

    if (a.av && !a.av.includes('default_profile')) {{
      node.shape = 'circularImage';
      node.image = a.av;
      node.borderWidth = isSynced ? 4 : 3;
      node.color = {{ border: color, highlight: {{ border: color }} }};
    }} else {{
      node.shape = 'dot';
      node.color = color;
      node.borderWidth = isSynced ? 4 : 2;
    }}
    return node;
  }});

  const nodeIds = new Set(nodes.map(n => n.id));
  const edges = DATA.edges.filter(e => nodeIds.has(e.s) && nodeIds.has(e.t)).map((e,i) => ({{
    id: 'e'+i, from: e.s, to: e.t,
    width: Math.min(e.w * 0.8, 5),
    title: `${{e.tp}} (peso: ${{e.w}})`,
    color: {{ color: EDGE_COLORS[e.tp]||'#ffffff33', highlight:'#ffffff88' }},
    arrows: {{ to: {{ enabled:true, scaleFactor:0.4 }} }},
    smooth: {{ type:'continuous' }},
  }}));

  const container = document.getElementById('graph');
  new vis.Network(container, {{ nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) }}, {{
    physics: {{
      forceAtlas2Based: {{ gravitationalConstant:-80, centralGravity:0.008, springLength:180, springConstant:0.06, damping:0.5 }},
      solver:'forceAtlas2Based',
      stabilization: {{ iterations:200 }},
    }},
    interaction: {{ hover:true, tooltipDelay:50, navigationButtons:true, zoomView:true }},
    edges: {{ smooth: {{ type:'continuous' }} }},
  }});
}}

// === SYNCED PATTERN ===
function buildSync() {{
  const synced = DATA.accounts.filter(a => a.tc === 34).sort((a,b) => a.u.localeCompare(b.u));
  const grid = document.getElementById('sync-grid');
  synced.forEach(a => {{
    const hasNum = /\\d{{4,}}/.test(a.u);
    const div = document.createElement('div');
    div.className = 'sync-item';
    const img = a.av && !a.av.includes('default_profile')
      ? `<img src="${{a.av}}" onerror="this.style.display='none'">`
      : `<div class="noav">?</div>`;
    div.innerHTML = `${{img}}<div><span style="color:#fff;font-weight:600"><a href="https://x.com/${{a.u}}" target="_blank">@${{a.u}}</a></span><br><span style="color:#888;font-size:11px">34 tweets${{hasNum?' &middot; <span style=color:#e74c3c>username numerico</span>':''}}</span></div>`;
    grid.appendChild(div);
  }});
}}

// === ACCOUNTS TABLE ===
function renderTable(accs) {{
  const tbody = document.getElementById('accounts-tbody');
  tbody.innerHTML = accs.map(a => {{
    const isSynced = a.tc === 34;
    const labelClass = isSynced ? 'synced' : (a.bl || '');
    const labelText = isSynced ? 'Patron 34' : (a.bl || 'N/A');
    const av = a.av && !a.av.includes('default_profile')
      ? `<img class="avatar" src="${{a.av}}" onerror="this.style.display='none'">`
      : '';
    return `<tr>
      <td>${{av}}<a href="https://x.com/${{a.u}}" target="_blank">@${{a.u}}</a><br><span style="color:#666;font-size:11px">${{a.dn}}</span></td>
      <td><span class="badge ${{labelClass}}">${{labelText}}</span></td>
      <td>${{a.bs.toFixed(3)}}</td>
      <td>${{a.tc.toLocaleString()}}</td>
      <td>${{a.fl.toLocaleString()}}</td>
      <td>${{a.fg.toLocaleString()}}</td>
      <td>${{a.ci ?? 'N/A'}}</td>
      <td>${{a.seed ? 'Si' : ''}}</td>
    </tr>`;
  }}).join('');
}}

function filterTable() {{
  const search = document.getElementById('search').value.toLowerCase();
  const label = document.getElementById('label-filter').value;
  const sort = document.getElementById('sort-filter').value;
  let filtered = DATA.accounts.filter(a => {{
    if (search && !a.u.toLowerCase().includes(search) && !(a.dn||'').toLowerCase().includes(search)) return false;
    if (label === 'synced') return a.tc === 34;
    if (label && a.bl !== label) return false;
    return true;
  }});
  if (sort === 'bs') filtered.sort((a,b) => b.bs - a.bs);
  else if (sort === 'tc') filtered.sort((a,b) => b.tc - a.tc);
  else if (sort === 'fl') filtered.sort((a,b) => b.fl - a.fl);
  else filtered.sort((a,b) => a.u.localeCompare(b.u));
  renderTable(filtered);
}}

// === COMMUNITIES ===
function buildCommunities() {{
  const comms = {{}};
  DATA.accounts.forEach(a => {{
    const c = a.ci ?? -1;
    if (!comms[c]) comms[c] = [];
    comms[c].push(a);
  }});
  const grid = document.getElementById('comm-grid');
  Object.entries(comms).sort((a,b) => b[1].length - a[1].length).forEach(([cid, members]) => {{
    if (cid == -1) return;
    const top = members.sort((a,b) => b.fl - a.fl).slice(0,5);
    const synced = members.filter(m => m.tc === 34).length;
    const avgScore = (members.reduce((s,m) => s+m.bs, 0) / members.length).toFixed(3);
    const card = document.createElement('div');
    card.className = 'comm-card';
    card.innerHTML = `
      <h4>Comunidad ${{cid}}</h4>
      <div style="display:flex;gap:16px;margin-bottom:8px;">
        <div><span style="font-size:20px;font-weight:700;color:#fff">${{members.length}}</span><br><span style="font-size:11px;color:#888">miembros</span></div>
        <div><span style="font-size:20px;font-weight:700;color:#f39c12">${{avgScore}}</span><br><span style="font-size:11px;color:#888">bot score prom</span></div>
        ${{synced ? `<div><span style="font-size:20px;font-weight:700;color:#9b59b6">${{synced}}</span><br><span style="font-size:11px;color:#888">patron 34</span></div>` : ''}}
      </div>
      <div style="font-size:12px;color:#aaa;">Top cuentas: ${{top.map(t=>`<a href="https://x.com/${{t.u}}" target="_blank">@${{t.u}}</a>`).join(', ')}}</div>
    `;
    grid.appendChild(card);
  }});
}}

// Init
buildGraph();
buildSync();
filterTable();
buildCommunities();
</script>
</body>
</html>"""

output = Path("data/exports/index.html")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(html, encoding="utf-8")
print(f"Single-page dashboard: {output} ({len(html)//1024}KB)")
