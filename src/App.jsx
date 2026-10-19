import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';

const nodes = {
  persona: { id: 'persona', title: 'persona-01', sub: 'Threat actor persona', x: 440, y: 260, color: 'blue', confidence: 'Medium', status: 'Needs review', type: 'Persona', detail: 'Primary persona', first: '2023-11-14', last: '2024-04-22', sources: 4 },
  alias: { id: 'alias', title: 'alias: nightjar', sub: 'Online alias', x: 185, y: 154, color: 'amber', confidence: 'Medium', status: 'Needs review', type: 'Online alias', detail: 'Marketplace handle', first: '2023-10-02', last: '2024-04-22', sources: 2 },
  pgp: { id: 'pgp', title: 'PGP key', sub: '0xA3F2...9D1C', x: 700, y: 139, color: 'emerald', confidence: 'High', status: 'Reviewed', type: 'Cryptographic key', detail: 'OpenPGP fingerprint', first: '2023-11-14', last: '2024-02-03', sources: 3 },
  wallet: { id: 'wallet', title: 'wallet', sub: 'bc1q...7h9k', x: 690, y: 386, color: 'amber', confidence: 'Low', status: 'Needs review', type: 'Financial identifier', detail: 'Synthetic wallet address', first: '2024-01-18', last: '2024-04-22', sources: 2 },
};

const edges = [
  { id: 'alias', a: 'persona', b: 'alias', label: 'controls', color: 'amber' },
  { id: 'pgp', a: 'persona', b: 'pgp', label: 'uses', color: 'emerald' },
  { id: 'wallet', a: 'persona', b: 'wallet', label: 'linked to', color: 'amber' },
];

const milestones = [
  { date: '2023-10-02', label: 'Alias first observed', color: 'cyan', node: 'alias' },
  { date: '2023-11-14', label: 'PGP key published', color: 'emerald', node: 'pgp', status: 'Reviewed' },
  { date: '2024-01-18', label: 'Wallet referenced', color: 'amber', node: 'wallet', status: 'Needs review' },
  { date: '2024-02-03', label: 'Key last observed', color: 'muted', node: 'pgp' },
  { date: '2024-04-22', label: 'Ongoing monitoring', color: 'dashed', node: 'persona' },
];

function Icon({ name, size = 18, strokeWidth = 1.7 }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true };
  const paths = {
    overview: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></>,
    graph: <><circle cx="5" cy="12" r="2.5"/><circle cx="19" cy="5" r="2.5"/><circle cx="19" cy="19" r="2.5"/><path d="m7.2 10.8 9.5-4.6M7.2 13.2l9.5 4.6"/></>,
    evidence: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h8"/></>,
    timeline: <><circle cx="6" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 6h8a2 2 0 0 1 2 2v8M16 18H8a2 2 0 0 1-2-2V8"/></>,
    reports: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/><path d="M8 7h8M8 11h8"/></>,
    saved: <><path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.6a8 8 0 0 1-1.6.9l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.6-.9l-1.7.6-1.4-2.4 1.4-1.1a7 7 0 0 1 0-1.9l-1.4-1.2 1.4-2.4 1.7.6a8 8 0 0 1 1.6-.9l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.6.9l1.7-.6 1.4 2.4-1.4 1.2a7 7 0 0 1-.1 1.8Z" transform="translate(-1 -1) scale(.96)"/></>,
    search: <><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 5 5"/></>,
    case: <><path d="M3 7h18v13H3zM8 7V4h8v3M3 11h18M10 11v2h4v-2"/></>,
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></>,
    alert: <><path d="m10.3 3.9-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3.1l-8-14a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    minus: <path d="M5 12h14"/>,
    center: <><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/><path d="M12 2v2M22 12h-2M12 22v-2M2 12h2"/></>,
    expand: <><path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M3 16v3a2 2 0 0 0 2 2h3"/></>,
    chevron: <path d="m9 18 6-6-6-6"/>,
    filter: <><path d="M4 5h16M7 12h10M10 19h4"/><circle cx="8" cy="5" r="1" fill="currentColor"/><circle cx="15" cy="12" r="1" fill="currentColor"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></>,
    key: <><circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M15 8l2 2M18 5l2 2"/></>,
    wallet: <><rect x="3" y="6" width="18" height="15" rx="2"/><path d="M3 10h18M16 15h.01M7 6V4a2 2 0 0 1 2-2h9"/></>,
    menu: <><path d="M4 6h16M4 12h16M4 18h16"/></>,
    close: <><path d="m18 6-12 12M6 6l12 12"/></>,
  };
  return <svg {...common}>{paths[name] || paths.overview}</svg>;
}

function Logo() {
  return <div className="brand"><div className="brand-mark"><span /></div><span>DarkLens</span><span className="brand-beta">INTEL</span></div>;
}

function Sidebar({ active, setActive, collapsed, setCollapsed, mobileOpen }) {
  const items = [
    ['Case Overview', 'overview'], ['Actor Graph', 'graph'], ['Evidence', 'evidence'], ['Timeline', 'timeline'], ['Reports', 'reports'], ['Saved Searches', 'saved'],
  ];
  return <aside className={`sidebar ${collapsed ? 'collapsed' : ''} ${mobileOpen ? 'mobile-open' : ''}`}>
    <div className="side-top"><Logo /><button className="icon-button collapse-button" onClick={() => setCollapsed(!collapsed)} aria-label="Collapse sidebar"><Icon name="menu" /></button></div>
    <div className="side-label">WORKSPACE</div>
    <nav className="nav-list" aria-label="Main navigation">
      {items.map(([label, icon]) => <button key={label} className={`nav-item ${active === label ? 'active' : ''}`} onClick={() => setActive(label)} title={collapsed ? label : undefined}>
        <span className="nav-indicator"/><Icon name={icon}/><span className="nav-text">{label}</span>{label === 'Evidence' && <span className="nav-count">4</span>}
      </button>)}
    </nav>
    <div className="side-divider" />
    <div className="side-label">PREFERENCES</div>
    <button className={`nav-item ${active === 'Settings' ? 'active' : ''}`} onClick={() => setActive('Settings')} title={collapsed ? 'Settings' : undefined}><span className="nav-indicator"/><Icon name="settings"/><span className="nav-text">Settings</span></button>
    <div className="sidebar-spacer" />
    <div className="side-foot"><div className="system-pulse"/><span className="nav-text">All systems nominal</span><span className="foot-version">v0.1</span></div>
  </aside>;
}

function Topbar({ setActive }) {
  const [query, setQuery] = useState('');
  const inputRef = useRef(null);
  useEffect(() => {
    const onKey = (e) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); inputRef.current?.focus(); } };
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey);
  }, []);
  return <header className="topbar">
    <div className="search-wrap"><Icon name="search" size={17}/><input ref={inputRef} aria-label="Search cases and entities" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search for actors, identifiers, domains, or cases..."/><kbd>⌘ K</kbd></div>
    <div className="top-actions"><span className="synthetic-pill"><span/>Synthetic data</span><button className="case-select" onClick={() => setActive('Case Overview')}><span className="case-dot"/><span className="case-select-label">Case: <b>DL-2024-0173</b></span><span className="down-chevron">⌄</span></button><button className="avatar-button" aria-label="Analyst profile">AN<span className="avatar-status"/></button></div>
  </header>;
}

function CountUp({ value }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    let frame;
    const started = performance.now();
    const step = now => {
      const progress = Math.min(1, (now - started) / 720);
      setCount(Math.round(value * (1 - Math.pow(1 - progress, 3))));
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [value]);
  return <motion.span>{count}</motion.span>;
}

function StatCard({ icon, eyebrow, title, children, accent, delay = 0, ring, count }) {
  return <motion.article className="stat-card panel" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .42, delay: delay / 1000, ease: [.2, .7, .2, 1] }}>
    <div className={`stat-icon ${accent}`}><Icon name={icon} size={18}/></div>
    <div className="stat-content"><div className="eyebrow">{eyebrow}</div><div className="stat-title">{count !== undefined && <CountUp value={count}/>} {title}</div><div className="stat-sub">{children}</div></div>
    {ring && <div className="progress-ring" style={{ '--progress': `${ring}%` }}><span>{ring}<small>%</small></span></div>}
  </motion.article>;
}

function GraphNode({ node, selected, dimmed, onSelect, onHover, onMove, zoom }) {
  const down = useRef(null);
  const isCenter = node.id === 'persona';
  const size = isCenter ? 58 : 47;
  const icon = node.id === 'pgp' ? 'key' : node.id === 'wallet' ? 'wallet' : node.id === 'alias' ? 'users' : 'overview';
  return <g className={`graph-node node-${node.color} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''}`} transform={`translate(${node.x} ${node.y})`} onMouseEnter={() => onHover(node.id)} onMouseLeave={() => onHover(null)} onClick={() => onSelect(node.id)} onPointerDown={e => { down.current = { x: e.clientX, y: e.clientY }; e.currentTarget.setPointerCapture?.(e.pointerId); }} onPointerMove={e => { if (!down.current || !(e.buttons & 1)) return; const rect = e.currentTarget.ownerSVGElement.getBoundingClientRect(); const scale = rect.width / 880 / zoom; onMove(node.id, (e.movementX / scale), (e.movementY / scale)); }} onPointerUp={e => { if (down.current) { const moved = Math.hypot(e.clientX - down.current.x, e.clientY - down.current.y); if (moved > 4) e.stopPropagation(); } down.current = null; }} role="button" tabIndex="0" aria-label={`${node.title}, ${node.confidence} confidence, ${node.status}`}>
    {isCenter && <circle className="node-pulse" r="45"/>}
    <circle className="node-halo" r={size + 8}/><circle className="node-core" r={size}/>
    <foreignObject x="-12" y="-12" width="24" height="24" className="node-glyph"><div className="node-icon-html"><Icon name={icon} size={20}/></div></foreignObject>
    <text className="node-title" textAnchor="middle" y={size + 22}>{node.title}</text>
    <text className="node-sub" textAnchor="middle" y={size + 40}>{node.sub}</text>
    <g className="node-status-tag" transform={`translate(-48 ${size + 49})`}><rect width="96" height="20" rx="10"/><text x="48" y="13" textAnchor="middle">{node.confidence.toUpperCase()} · {node.status === 'Reviewed' ? 'REVIEWED' : 'REVIEW'}</text></g>
    <title>{node.title} — {node.detail}. {node.confidence} review priority.</title>
  </g>;
}

function ActorGraph({ selected, setSelected, activeMilestone }) {
  const [hovered, setHovered] = useState(null);
  const [positions, setPositions] = useState(nodes);
  const [zoom, setZoom] = useState(1);
  const [layout, setLayout] = useState('Force directed');
  const [fullscreen, setFullscreen] = useState(false);
  const wrapRef = useRef(null);
  const nodeList = Object.values(positions);
  const active = hovered || selected;
  const reposition = (id, dx, dy) => setPositions(old => ({ ...old, [id]: { ...old[id], x: Math.min(830, Math.max(48, old[id].x + dx)), y: Math.min(470, Math.max(52, old[id].y + dy)) } }));
  const recenter = () => { setPositions(nodes); setZoom(1); };
  useEffect(() => { if (!fullscreen) return; const key = e => { if (e.key === 'Escape') setFullscreen(false); }; window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key); }, [fullscreen]);
  return <motion.section ref={wrapRef} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5, delay: .22 }} className={`graph-card panel ${fullscreen ? 'graph-fullscreen' : ''}`}>
    <div className="panel-heading graph-heading"><div><div className="eyebrow">RELATIONSHIP MAPPING</div><h2><span className="heading-orb"><Icon name="graph" size={17}/></span>Actor Graph</h2></div>
      <div className="graph-tools"><label className="layout-select"><select aria-label="Graph layout" value={layout} onChange={e => setLayout(e.target.value)}><option>Force directed</option><option>Radial</option><option>Timeline</option></select><span>⌄</span></label><button className="icon-button" onClick={recenter} title="Recenter graph" aria-label="Recenter graph"><Icon name="center" size={16}/></button><button className="icon-button" onClick={() => setZoom(v => Math.min(1.45, +(v + .1).toFixed(1)))} title="Zoom in" aria-label="Zoom in"><Icon name="plus" size={16}/></button><button className="icon-button" onClick={() => setZoom(v => Math.max(.75, +(v - .1).toFixed(1)))} title="Zoom out" aria-label="Zoom out"><Icon name="minus" size={16}/></button><button className="icon-button" onClick={() => setFullscreen(!fullscreen)} title="Toggle fullscreen" aria-label="Toggle graph fullscreen"><Icon name="expand" size={16}/></button></div>
    </div>
    <div className="graph-stage">
      <div className="scan-lines"/><div className="graph-top-tags"><span className="graph-case-tag"><i/>CASE DL-2024-0173</span><span className="graph-live"><i/>LINK ANALYSIS</span></div>
      <svg className="graph-svg" viewBox="0 0 880 520" role="img" aria-label="Interactive relationship graph. Select or drag nodes to explore synthetic evidence." style={{ '--zoom': zoom }}>
        <defs><linearGradient id="edgeGradient" x1="0" x2="1"><stop offset="0" stopColor="#3B82F6"/><stop offset=".52" stopColor="#22D3EE"/><stop offset="1" stopColor="#10B981"/></linearGradient><filter id="glow"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter><pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".7" fill="#27405e" opacity=".62"/></pattern></defs>
        <rect width="880" height="520" fill="url(#dots)" opacity=".8"/>
        <g transform={`translate(${440 - 440 * zoom},${260 - 260 * zoom}) scale(${zoom})`}>
          {edges.map(edge => { const a = positions[edge.a], b = positions[edge.b], isHot = active === edge.a || active === edge.b; const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2; return <g key={edge.id} className={`graph-edge ${isHot ? 'hot' : ''} ${active && !isHot ? 'edge-dim' : ''}`}>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="edge-base"/><line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={`edge-glow ${edge.color}`}/><circle r="3" className={`edge-particle ${edge.color}`}><animateMotion dur={`${3.5 + edges.indexOf(edge)}s`} repeatCount="indefinite" path={`M${a.x},${a.y} L${b.x},${b.y}`}/></circle>
            <g className="edge-label" transform={`translate(${mx - 34} ${my - 11})`}><rect width="68" height="22" rx="7"/><text x="34" y="15" textAnchor="middle">{edge.label}</text></g>
          </g>; })}
          {nodeList.map(n => <GraphNode key={n.id} node={n} zoom={zoom} selected={selected === n.id || activeMilestone === n.id} dimmed={!!active && active !== n.id && !edges.some(e => (e.a === active && e.b === n.id) || (e.b === active && e.a === n.id))} onSelect={setSelected} onHover={setHovered} onMove={reposition}/>)}
        </g>
      </svg>
      <div className="graph-legend"><span><i className="legend-dot blue"/>Persona</span><span><i className="legend-dot emerald"/>Identifier</span><span><i className="legend-dot amber"/>Needs review</span><span><i className="legend-dot grey"/>Other</span></div>
      <div className="minimap"><div className="mini-node mini-a"/><div className="mini-node mini-b"/><div className="mini-node mini-c"/><div className="mini-node mini-d"/><i/></div>
      {hovered && <div className="graph-tooltip"><span>{positions[hovered].title}</span><small>{positions[hovered].detail} · {positions[hovered].status}</small></div>}
    </div>
    <div className="graph-footer"><span><i className="footer-live-dot"/> 4 entities <b>·</b> 3 relationships</span><span>Drag nodes to arrange <b>·</b> Select a node for evidence</span></div>
  </motion.section>;
}

function EvidencePanel({ selected, setSelected }) {
  const node = nodes[selected] || nodes.pgp;
  const isKey = node.id === 'pgp';
  const confidence = isKey ? 'High' : node.confidence;
  const color = isKey ? 'emerald' : node.color;
  const evidence = isKey ? [
    { title: 'Public key fingerprint observed', meta: 'Synthetic archive · Nov 14, 2023', status: 'Reviewed', score: '0.92', icon: 'key' },
    { title: 'Same key on second marketplace', meta: 'Forum snapshot · Jan 08, 2024', status: 'Reviewed', score: '0.88', icon: 'evidence' },
    { title: 'Key reused by persona-01', meta: 'Synthetic profile · Feb 03, 2024', status: 'Reviewed', score: '0.84', icon: 'graph' },
  ] : [
    { title: `${node.detail} observed`, meta: `Synthetic archive · ${node.first}`, status: node.status, score: node.confidence === 'Low' ? '0.34' : '0.62', icon: node.id === 'wallet' ? 'wallet' : 'users' },
    { title: `Activity linked to ${node.title}`, meta: `Synthetic profile · ${node.last}`, status: 'Needs review', score: '0.51', icon: 'graph' },
    { title: 'Cross-source mention', meta: 'Synthetic forum · Mar 12, 2024', status: 'Reviewed', score: '0.73', icon: 'evidence' },
  ];
  const icon = node.id === 'pgp' ? 'key' : node.id === 'wallet' ? 'wallet' : node.id === 'alias' ? 'users' : 'overview';
  return <motion.aside initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5, delay: .28 }} className="evidence-card panel">
    <div className="evidence-top"><div><div className="eyebrow">SELECTED IDENTIFIER</div><h2>Evidence Detail</h2></div><button className="icon-button" aria-label="More evidence options">···</button></div>
    <div className="detail-entity"><div className={`entity-icon ${color}`}><Icon name={icon} size={19}/></div><div className="entity-titles"><div className="entity-name">{node.id === 'pgp' ? 'PGP key' : node.title}</div><div className="entity-type">{node.id === 'pgp' ? 'Cryptographic key' : node.detail}</div><div className="entity-id mono">{node.id === 'pgp' ? '0xA3F2...9D1C' : node.id === 'wallet' ? 'bc1q...7h9k' : node.id === 'persona' ? 'ACTOR · DL-001' : '@nightjar'}</div></div></div>
    <div className="detail-meta-grid"><div><span className="eyebrow">FIRST SEEN</span><b className="mono">{node.id === 'pgp' ? '2023-11-14' : node.first}</b></div><div><span className="eyebrow">LAST SEEN</span><b className="mono">{node.id === 'pgp' ? '2024-02-03' : node.last}</b></div><div><span className="eyebrow">SOURCES</span><b className="mono">{node.id === 'pgp' ? 3 : node.sources}</b></div></div>
    <div className="confidence-row"><div><span className="eyebrow">CONFIDENCE</span><span className="info-tip" tabIndex="0" aria-label="Review priority, not proof of identity"><Icon name="info" size={13}/><span className="tooltip-text">Review priority, not proof of identity.</span></span></div><span className={`status-pill ${color}`}><i/>{confidence}</span></div>
    <div className="related-row"><span className="eyebrow">RELATED TO</span><button className="related-chip" onClick={() => setSelected('persona')}><span className="related-avatar"><Icon name="overview" size={13}/></span><span>persona-01</span><span className="related-likelihood">Likely</span><Icon name="chevron" size={13}/></button></div>
    <div className="evidence-list-heading"><div><h3>Evidence items <span>(3)</span></h3><span className="evidence-caption">Signals supporting this record</span></div><button className="text-link" onClick={() => setSelected(node.id)}>View all <Icon name="chevron" size={13}/></button></div>
    <div className="evidence-list">{evidence.map((item, i) => <article className="evidence-item" key={`${node.id}-${i}`}><div className={`evidence-item-icon ${i === 0 ? 'cyan' : i === 1 ? 'blue' : 'emerald'}`}><Icon name={item.icon} size={15}/></div><div className="evidence-item-main"><div className="evidence-item-title">{item.title}</div><div className="evidence-item-meta">{item.meta}</div></div><div className="evidence-item-end"><span className="evidence-score">{item.score}</span><span className={`mini-status ${item.status === 'Reviewed' ? 'reviewed' : 'needs-review'}`}>{item.status === 'Reviewed' ? 'Reviewed' : 'Needs review'}</span></div></article>)}</div>
    <div className="source-foot"><div className="source-icon"><Icon name="database" size={15}/></div><div><span className="eyebrow">SOURCE RELIABILITY</span><b>3 synthetic sources <span className="reliability-bars"><i/><i/><i/></span></b></div><span className="source-grade">HIGH</span></div>
    <div className="review-note"><span className="review-note-icon"><Icon name="info" size={14}/></span><span>Links are investigative leads for analyst review, not proof of identity.</span></div>
  </motion.aside>;
}

function Timeline({ selectedMilestone, setSelectedMilestone }) {
  const [range, setRange] = useState('Full range');
  return <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5, delay: .34 }} className="timeline-card panel"><div className="timeline-header"><div><div className="eyebrow">OBSERVATION HISTORY</div><h2><span className="heading-orb timeline-icon"><Icon name="timeline" size={16}/></span>Timeline</h2></div><div className="timeline-controls"><span className="timeline-range mono">2023-10-02 <i>→</i> 2024-04-22</span><label className="range-select"><select value={range} onChange={e => setRange(e.target.value)} aria-label="Timeline range"><option>Full range</option><option>Last 90 days</option><option>Last 30 days</option></select><span>⌄</span></label></div></div>
    <div className="timeline-scroll"><div className="timeline-track"><div className="timeline-line"/><div className="timeline-fill"/>{milestones.map((m, i) => <button key={m.date} className={`milestone ${m.color} ${selectedMilestone === m.node ? 'milestone-active' : ''}`} style={{ left: `${i * 24 + 2}%` }} onClick={() => { setSelectedMilestone(m.node); }} aria-label={`${m.date}: ${m.label}`}><span className="milestone-dot"/><span className="milestone-date mono">{m.date}</span><span className="milestone-label">{m.label}</span>{m.status && <span className={`milestone-status ${m.status === 'Reviewed' ? 'reviewed' : 'needs-review'}`}>{m.status}</span>}</button>)}</div></div>
    <div className="timeline-foot"><span><i className="footer-live-dot"/> 5 observations <b>·</b> 1 ongoing</span><button className="text-link" onClick={() => setSelectedMilestone('persona')}>Open full timeline <Icon name="chevron" size={13}/></button></div>
  </motion.section>;
}

export default function App() {
  const [active, setActive] = useState('Case Overview');
  const [selected, setSelected] = useState('pgp');
  const [selectedMilestone, setSelectedMilestone] = useState(null);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const mainRef = useRef(null);
  useEffect(() => {
    if (!selectedMilestone) return;
    setSelected(selectedMilestone);
  }, [selectedMilestone]);
  const progress = useMemo(() => 67, []);
  return <div className="app-shell">
    <div className="ambient ambient-one"/><div className="ambient ambient-two"/><div className="particle particle-one"/><div className="particle particle-two"/><div className="particle particle-three"/>
    <Sidebar active={active} setActive={setActive} collapsed={collapsed} setCollapsed={setCollapsed} mobileOpen={mobileOpen}/>
    {mobileOpen && <button className="mobile-scrim" onClick={() => setMobileOpen(false)} aria-label="Close navigation"/>}
    <div className="main-column" ref={mainRef}>
      <div className="mobile-header"><button className="icon-button" onClick={() => setMobileOpen(!mobileOpen)} aria-label="Open navigation"><Icon name="menu"/></button><Logo/><span className="synthetic-pill"><span/>Synthetic data</span></div>
      <Topbar setActive={setActive}/>
      <main className="main-content">
        <div className="page-title-row enter"><div><div className="breadcrumbs"><span>Workspace</span><Icon name="chevron" size={12}/><span>Cases</span><Icon name="chevron" size={12}/><b>DL-2024-0173</b></div><h1>Case Overview <span className="case-number mono">DL-2024-0173</span></h1><p>Evidence-backed leads for analyst review <span className="title-separator">/</span> <span className="synthetic-inline"><i/> Synthetic case</span></p></div><button className="export-button" onClick={() => { const blob = new Blob([JSON.stringify({ case: 'DL-2024-0173', synthetic: true, entities: Object.values(nodes).map(({ id, title, type, confidence, status }) => ({ id, title, type, confidence, status })), evidence: ['key fingerprint observed', 'key reused across sources', 'wallet referenced'] }, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'darklens-case-DL-2024-0173.json'; a.click(); URL.revokeObjectURL(url); }}><Icon name="evidence" size={15}/>Export case</button></div>
        <div className="stats-grid">
          <StatCard icon="case" eyebrow="ACTIVE CASE" title="DarkLens Case" accent="cyan" delay={40}><span className="mono">DL-2024-0173</span><span className="stat-dot-separator">·</span><span className="synthetic-mini"><i/>Synthetic data</span></StatCard>
          <StatCard icon="users" eyebrow="LINKED ENTITIES" title="Entities" accent="blue" delay={90} count={3}><span>1 persona</span><span className="stat-dot-separator">·</span><span>2 identifiers</span></StatCard>
          <StatCard icon="database" eyebrow="EVIDENCE ITEMS" title="Signals" accent="emerald" delay={140} count={12}><span className="good-text">8 reviewed</span><span className="stat-dot-separator">·</span><span className="warn-text">4 need review</span></StatCard>
          <StatCard icon="alert" eyebrow="REVIEW PROGRESS" title="Analyst review" accent="amber" delay={190} ring={progress}><span>8 of 12 evidence items reviewed</span></StatCard>
        </div>
        <div className="workspace-grid"><ActorGraph selected={selected} setSelected={setSelected} activeMilestone={selectedMilestone}/><EvidencePanel selected={selected} setSelected={setSelected}/></div>
        <Timeline selectedMilestone={selectedMilestone} setSelectedMilestone={setSelectedMilestone}/>
        <footer className="page-footer"><span><Logo/><span className="footer-copy">© 2024 DarkLens Intelligence Workspace</span></span><span className="footer-right"><i className="system-pulse"/> Synthetic environment <span className="footer-divider"/> Data is illustrative and generated for demonstration</span></footer>
      </main>
    </div>
  </div>;
}
