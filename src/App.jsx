import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { getCases, getCase, getTimeline, exportCase, reviewLink, saveAnalysis, importCaseBundle, previewCaseBundle } from './api';

const CASE_ID = 'NIGHTJAR-2026-001';

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

function Sidebar({ active, setActive, collapsed, setCollapsed, mobileOpen, evidenceCount = 0, pendingCount = 0 }) {
  const items = [
    ['Case Overview', 'overview'], ['Actor Graph', 'graph'], ['Evidence', 'evidence'], ['Review Queue', 'filter'], ['Timeline', 'timeline'], ['Reports', 'reports'], ['Saved Searches', 'saved'],
  ];
  return <aside className={`sidebar ${collapsed ? 'collapsed' : ''} ${mobileOpen ? 'mobile-open' : ''}`}>
    <div className="side-top"><Logo /><button className="icon-button collapse-button" onClick={() => setCollapsed(!collapsed)} aria-label="Collapse sidebar"><Icon name="menu" /></button></div>
    <div className="side-label">WORKSPACE</div>
    <nav className="nav-list" aria-label="Main navigation">
      {items.map(([label, icon]) => <button key={label} className={`nav-item ${active === label ? 'active' : ''}`} onClick={() => setActive(label)} title={collapsed ? label : undefined}>
        <span className="nav-indicator"/><Icon name={icon}/><span className="nav-text">{label}</span>{label === 'Evidence' && <span className="nav-count">{evidenceCount}</span>}{label === 'Review Queue' && <span className="nav-count">{pendingCount}</span>}
      </button>)}
    </nav>
    <div className="side-divider" />
    <div className="side-label">PREFERENCES</div>
    <button className={`nav-item ${active === 'Settings' ? 'active' : ''}`} onClick={() => setActive('Settings')} title={collapsed ? 'Settings' : undefined}><span className="nav-indicator"/><Icon name="settings"/><span className="nav-text">Settings</span></button>
    <div className="sidebar-spacer" />
    <div className="side-foot"><div className="system-pulse"/><span className="nav-text">All systems nominal</span><span className="foot-version">v0.1</span></div>
  </aside>;
}

function Topbar({ setActive, caseTitle, query, setQuery, entities = [], cases = [], onSelectEntity, onSelectCase, openPanel }) {
  const inputRef = useRef(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [caseOpen, setCaseOpen] = useState(false);
  const results = query.trim() ? entities.filter(entity => `${entity.display_label} ${entity.id} ${entity.type}`.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 7) : [];
  useEffect(() => {
    const onKey = (e) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); inputRef.current?.focus(); } };
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey);
  }, []);
  return <header className="topbar">
    <div className="search-wrap"><Icon name="search" size={17}/><input ref={inputRef} aria-label="Search cases and entities" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search for actors, identifiers, domains, or cases..."/><kbd>⌘ K</kbd>{results.length > 0 && <div className="search-results">{results.map(entity => <button key={entity.id} onClick={() => { onSelectEntity(entity.id); setQuery(''); setActive('Actor Graph'); }}><b>{entity.display_label}</b><small>{entity.type.replaceAll('_',' ')} · {entity.id}</small></button>)}</div>}{query.trim() && results.length === 0 && <div className="search-results"><span>No matching records in this case</span></div>}</div>
    <div className="top-actions"><span className="synthetic-pill"><span/>Synthetic data</span><div className="top-popover-wrap"><button className="case-select" onClick={() => setCaseOpen(v => !v)}><span className="case-dot"/><span className="case-select-label">Case: <b>{caseTitle || CASE_ID}</b></span><span className="down-chevron">⌄</span></button>{caseOpen && <div className="top-popover case-popover"><b>Choose a synthetic case</b>{cases.map(item => <button className={item.id === caseTitle ? 'current-case-option' : ''} key={item.id} onClick={() => { onSelectCase(item.id); setCaseOpen(false); setActive('Case Overview'); }}><span>{item.title}</span><small>{item.id}</small></button>)}<button onClick={() => { openPanel('Import JSON'); setCaseOpen(false); }}>Import JSON case…</button></div>}</div><div className="top-popover-wrap"><button className="avatar-button" aria-label="Analyst profile" onClick={() => setProfileOpen(v => !v)}>AN<span className="avatar-status"/></button>{profileOpen && <div className="top-popover profile-popover"><b>Demo analyst</b><span>Local synthetic workspace</span><button onClick={() => { openPanel('Settings'); setProfileOpen(false); }}>Workspace settings</button></div>}</div></div>
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
  const isCenter = node.type === 'persona' || node.id === 'persona';
  const size = isCenter ? 45 : 32;
  const icon = node.type === 'pgp_key' || node.id === 'pgp' ? 'key' : node.type === 'wallet' || node.id === 'wallet' ? 'wallet' : ['handle', 'persona'].includes(node.type) || ['alias', 'persona'].includes(node.id) ? 'users' : 'database';
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

function ActorGraph({ selected, setSelected, activeMilestone, caseData, showEvidenceEdges = true }) {
  const [hovered, setHovered] = useState(null);
  const [positions, setPositions] = useState(nodes);
  const [zoom, setZoom] = useState(1);
  const [layout, setLayout] = useState('Force directed');
  const [fullscreen, setFullscreen] = useState(false);
  const wrapRef = useRef(null);
  const graphEntities = caseData ? (() => {
    const connected = new Set([
      ...caseData.links.flatMap(link => [link.from_entity_id, link.to_entity_id]),
      ...(caseData.evidence_associations || []).flatMap(edge => [edge.from_entity_id, edge.to_entity_id]),
    ]);
    const evidenceIds = new Set(caseData.links.flatMap(link => link.evidence_ids));
    caseData.evidence.filter(item => evidenceIds.has(item.id)).forEach(item => {
      if (item.entity_id) connected.add(item.entity_id);
      if (item.details?.actor_entity_id) connected.add(item.details.actor_entity_id);
      ['key', 'wallet'].forEach(field => { if (item.details?.[field]) connected.add(item.details[field]); });
    });
    const relevant = caseData.entities.filter(entity => connected.has(entity.id));
    return relevant.map((entity, index) => {
      const angle = -Math.PI / 2 + index * (Math.PI * 2 / relevant.length);
      const observationIds = new Set(caseData.evidence.filter(item => item.entity_id === entity.id || item.details?.key === entity.id || item.details?.wallet === entity.id).map(item => item.id));
      const associated = caseData.links.filter(link => link.from_entity_id === entity.id || link.to_entity_id === entity.id || link.evidence_ids.some(id => observationIds.has(id)));
      const best = Math.max(0, ...associated.map(link => link.score));
      const status = associated.some(link => link.review_status === 'accepted') ? 'Reviewed' : 'Needs review';
      const typeColor = entity.type === 'persona' ? 'blue' : entity.type === 'handle' ? 'amber' : ['pgp_key', 'wallet'].includes(entity.type) ? 'emerald' : 'cyan';
      return { id: entity.id, title: entity.display_label, sub: entity.type.replaceAll('_', ' '), type: entity.type, detail: Object.entries(entity.attributes || {}).filter(([key]) => key !== 'synthetic').map(([key, value]) => `${key}: ${value}`).join(' · ') || entity.type, x: 440 + Math.cos(angle) * 255, y: 260 + Math.sin(angle) * 170, color: typeColor, confidence: best >= .85 ? 'High' : best >= .4 ? 'Medium' : 'Low', status, first: entity.first_seen || '—', last: entity.last_seen || '—', sources: associated.length };
    });
  })() : Object.values(nodes);
  const graphEdges = caseData ? [
    ...caseData.links.map(link => ({ id: link.id, a: link.from_entity_id, b: link.to_entity_id, label: `candidate · ${link.relation.replaceAll('_', ' ')}`, color: link.score >= .85 ? 'emerald' : link.score >= .4 ? 'amber' : 'cyan', kind: 'candidate' })),
    ...(showEvidenceEdges ? (caseData.evidence_associations || []).map(edge => ({ id: `association-${edge.from_entity_id}-${edge.to_entity_id}`, a: edge.from_entity_id, b: edge.to_entity_id, label: 'evidence association', color: 'grey', kind: 'association' })) : []),
  ] : edges;
  const layoutNodes = () => {
    if (layout === 'Force directed' || !caseData) return graphEntities;
    const sorted = layout === 'Timeline' ? [...graphEntities].sort((a, b) => a.first.localeCompare(b.first)) : graphEntities;
    return sorted.map((node, index) => {
      const angle = -Math.PI / 2 + index * (Math.PI * 2 / sorted.length);
      const x = layout === 'Timeline' ? 65 + index * (750 / Math.max(1, sorted.length - 1)) : 440 + Math.cos(angle) * 300;
      const y = layout === 'Timeline' ? 130 + (index % 3) * 125 : 260 + Math.sin(angle) * 185;
      return { ...node, x, y };
    });
  };
  useEffect(() => { setPositions(Object.fromEntries(layoutNodes().map(node => [node.id, node]))); }, [caseData, layout]);
  const nodeList = caseData ? graphEntities.map(node => positions[node.id] || node) : Object.values(positions);
  const active = hovered || selected;
  const reposition = (id, dx, dy) => setPositions(old => ({ ...old, [id]: { ...old[id], x: Math.min(830, Math.max(48, old[id].x + dx)), y: Math.min(470, Math.max(52, old[id].y + dy)) } }));
  const recenter = () => { setPositions(Object.fromEntries(layoutNodes().map(node => [node.id, node]))); setZoom(1); };
  useEffect(() => { if (!fullscreen) return; const key = e => { if (e.key === 'Escape') setFullscreen(false); }; window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key); }, [fullscreen]);
  return <motion.section id="graph" ref={wrapRef} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5, delay: .22 }} className={`graph-card panel ${fullscreen ? 'graph-fullscreen' : ''}`}>
    <div className="panel-heading graph-heading"><div><div className="eyebrow">RELATIONSHIP MAPPING</div><h2><span className="heading-orb"><Icon name="graph" size={17}/></span>Actor Graph</h2></div>
      <div className="graph-tools"><label className="layout-select"><select aria-label="Graph layout" value={layout} onChange={e => setLayout(e.target.value)}><option>Force directed</option><option>Radial</option><option>Timeline</option></select><span>⌄</span></label><button className="icon-button" onClick={recenter} title="Recenter graph" aria-label="Recenter graph"><Icon name="center" size={16}/></button><button className="icon-button" onClick={() => setZoom(v => Math.min(1.45, +(v + .1).toFixed(1)))} title="Zoom in" aria-label="Zoom in"><Icon name="plus" size={16}/></button><button className="icon-button" onClick={() => setZoom(v => Math.max(.75, +(v - .1).toFixed(1)))} title="Zoom out" aria-label="Zoom out"><Icon name="minus" size={16}/></button><button className="icon-button" onClick={() => setFullscreen(!fullscreen)} title="Toggle fullscreen" aria-label="Toggle graph fullscreen"><Icon name="expand" size={16}/></button></div>
    </div>
    <div className="graph-stage">
      <div className="scan-lines"/><div className="graph-top-tags"><span className="graph-case-tag"><i/>CASE {caseData?.case.id || CASE_ID}</span><span className="graph-live"><i/>LINK ANALYSIS</span></div>
      <svg className="graph-svg" viewBox="0 0 880 520" role="img" aria-label="Interactive relationship graph. Select or drag nodes to explore synthetic evidence." style={{ '--zoom': zoom }}>
        <defs><linearGradient id="edgeGradient" x1="0" x2="1"><stop offset="0" stopColor="#3B82F6"/><stop offset=".52" stopColor="#22D3EE"/><stop offset="1" stopColor="#10B981"/></linearGradient><filter id="glow"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter><pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".7" fill="#27405e" opacity=".62"/></pattern></defs>
        <rect width="880" height="520" fill="url(#dots)" opacity=".8"/>
        <g transform={`translate(${440 - 440 * zoom},${260 - 260 * zoom}) scale(${zoom})`}>
          {graphEdges.map(edge => { const a = positions[edge.a], b = positions[edge.b]; if (!a || !b) return null; const isHot = active === edge.a || active === edge.b; const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2; return <g key={edge.id} className={`graph-edge ${edge.kind || ''} ${isHot ? 'hot' : ''} ${active && !isHot ? 'edge-dim' : ''}`}>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="edge-base"/><line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={`edge-glow ${edge.color}`}/><circle r="3" className={`edge-particle ${edge.color}`}><animateMotion dur={`${3.5 + edges.indexOf(edge)}s`} repeatCount="indefinite" path={`M${a.x},${a.y} L${b.x},${b.y}`}/></circle>
            <g className="edge-label" transform={`translate(${mx - 34} ${my - 11})`}><rect width="68" height="22" rx="7"/><text x="34" y="15" textAnchor="middle">{edge.label}</text></g>
          </g>; })}
          {nodeList.map(n => <GraphNode key={n.id} node={n} zoom={zoom} selected={selected === n.id || activeMilestone === n.id} dimmed={!!active && active !== n.id && !graphEdges.some(e => (e.a === active && e.b === n.id) || (e.b === active && e.a === n.id))} onSelect={setSelected} onHover={setHovered} onMove={reposition}/>)}
        </g>
      </svg>
      <div className="graph-legend"><span><i className="legend-dot blue"/>Persona</span><span><i className="legend-dot emerald"/>Identifier</span><span><i className="legend-dot amber"/>Needs review</span><span><i className="legend-dot grey"/>Other</span></div>
      <div className="minimap"><div className="mini-node mini-a"/><div className="mini-node mini-b"/><div className="mini-node mini-c"/><div className="mini-node mini-d"/><i/></div>
      {hovered && <div className="graph-tooltip"><span>{positions[hovered].title}</span><small>{positions[hovered].detail} · {positions[hovered].status}</small></div>}
    </div>
      <div className="graph-footer"><span><i className="footer-live-dot"/> {nodeList.length} entities <b>·</b> {caseData?.links.length || 0} candidate links <b>·</b> {caseData?.evidence_associations?.length || 0} evidence associations</span><span>Associations are evidence paths, not attribution conclusions</span></div>
  </motion.section>;
}

function EvidencePanel({ selected, setSelected, caseData, onReviewLink, reviewBusy }) {
  const listRef = useRef(null);
  const [moreOpen, setMoreOpen] = useState(false);
  const fixtureNode = nodes[selected] || nodes.pgp;
  const apiEntity = caseData?.entities?.find(entity => entity.id === selected || entity.id === ({ persona: 'actor-a', alias: 'handle-mothlight', pgp: 'key-fp1', wallet: 'wallet-w1' })[selected]);
  const apiEntityId = apiEntity?.id;
  const entityEvidence = caseData?.evidence?.filter(item => item.entity_id === apiEntityId || item.details?.key === apiEntityId || item.details?.wallet === apiEntityId) || [];
  const entityEvidenceIds = new Set(entityEvidence.map(item => item.id));
  const relatedLinks = caseData?.links?.filter(link => link.from_entity_id === apiEntityId || link.to_entity_id === apiEntityId || link.evidence_ids.some(id => entityEvidenceIds.has(id))) || [];
  const entityScore = Math.max(0, ...relatedLinks.map(link => link.score));
  const apiColor = apiEntity?.type === 'persona' ? 'blue' : apiEntity?.type === 'handle' ? 'amber' : ['pgp_key', 'wallet'].includes(apiEntity?.type) ? 'emerald' : 'cyan';
  const confidenceColor = entityScore >= .85 ? 'emerald' : entityScore >= .4 ? 'amber' : 'red';
  const node = apiEntity ? { id: apiEntity.id, title: apiEntity.display_label, detail: apiEntity.type.replaceAll('_', ' '), color: apiColor, confidence: entityScore >= .85 ? 'High' : entityScore >= .4 ? 'Medium' : 'Low', status: relatedLinks.some(link => link.review_status === 'accepted') ? 'Reviewed' : 'Needs review', first: apiEntity.first_seen || '—', last: apiEntity.last_seen || '—', sources: 0 } : fixtureNode;
  const isKey = apiEntity?.type === 'pgp_key' || node.id === 'pgp';
  const confidence = node.confidence;
  const color = node.color;
  const fixtureEvidence = isKey ? [
    { title: 'Public key fingerprint observed', meta: 'Synthetic archive · Nov 14, 2023', status: 'Reviewed', score: '0.92', icon: 'key' },
    { title: 'Same key on second marketplace', meta: 'Forum snapshot · Jan 08, 2024', status: 'Reviewed', score: '0.88', icon: 'evidence' },
    { title: 'Key reused by persona-01', meta: 'Synthetic profile · Feb 03, 2024', status: 'Reviewed', score: '0.84', icon: 'graph' },
  ] : [
    { title: `${node.detail} observed`, meta: `Synthetic archive · ${node.first}`, status: node.status, score: node.confidence === 'Low' ? '0.34' : '0.62', icon: node.id === 'wallet' ? 'wallet' : 'users' },
    { title: `Activity linked to ${node.title}`, meta: `Synthetic profile · ${node.last}`, status: 'Needs review', score: '0.51', icon: 'graph' },
    { title: 'Cross-source mention', meta: 'Synthetic forum · Mar 12, 2024', status: 'Reviewed', score: '0.73', icon: 'evidence' },
  ];
  const apiEvidence = caseData?.evidence?.filter(item => entityEvidenceIds.has(item.id) || (caseData.links || []).some(link => link.evidence_ids.includes(item.id) && relatedLinks.some(related => related.id === link.id))) || [];
  const sourceReliability = apiEvidence.length ? apiEvidence.reduce((sum, item) => sum + (caseData.sources.find(source => source.id === item.source_id)?.reliability || 0), 0) / apiEvidence.length : 0;
  const sourceGrade = sourceReliability >= .8 ? 'HIGH' : sourceReliability >= .6 ? 'MODERATE' : 'LOW';
  const evidence = apiEvidence.length ? apiEvidence.map(item => ({
    title: item.summary,
    meta: `${item.evidence_type.replaceAll('_', ' ')} · ${item.observed_at}`,
    status: (() => { const status = caseData.links.find(link => link.evidence_ids.includes(item.id))?.review_status; return status === 'accepted' ? 'Reviewed' : status === 'rejected' ? 'Rejected' : status === 'needs_more_evidence' ? 'More evidence' : 'Needs review'; })(),
    score: Number(item.confidence).toFixed(2),
    icon: item.evidence_type.includes('wallet') ? 'wallet' : item.evidence_type.includes('pgp') ? 'key' : 'evidence',
  })) : fixtureEvidence;
  const icon = apiEntity?.type === 'pgp_key' || node.id === 'pgp' ? 'key' : apiEntity?.type === 'wallet' || node.id === 'wallet' ? 'wallet' : ['handle', 'persona'].includes(apiEntity?.type) || ['alias', 'persona'].includes(node.id) ? 'users' : 'database';
  return <motion.aside id="evidence" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5, delay: .28 }} className="evidence-card panel">
    <div className="evidence-top"><div><div className="eyebrow">{apiEntity ? 'SELECTED RECORD' : 'SELECTED IDENTIFIER'}</div><h2>Evidence Detail</h2></div><div className="more-wrap"><button className="icon-button" aria-label="More evidence options" onClick={() => setMoreOpen(v => !v)}>···</button>{moreOpen && <div className="more-menu"><button onClick={() => { navigator.clipboard?.writeText(apiEntity?.id || node.id); setMoreOpen(false); }}>Copy record ID</button><button onClick={() => { window.print(); setMoreOpen(false); }}>Print case view</button></div>}</div></div>
    <div className="detail-entity"><div className={`entity-icon ${color}`}><Icon name={icon} size={19}/></div><div className="entity-titles"><div className="entity-name">{node.title}</div><div className="entity-type">{apiEntity?.type || node.detail}</div><div className="entity-id mono">{apiEntity?.id || node.id}</div></div></div>
    <div className="detail-meta-grid"><div><span className="eyebrow">FIRST SEEN</span><b className="mono">{apiEntity?.first_seen || node.first}</b></div><div><span className="eyebrow">LAST SEEN</span><b className="mono">{apiEntity?.last_seen || node.last}</b></div><div><span className="eyebrow">SOURCES</span><b className="mono">{apiEvidence.length ? new Set(apiEvidence.map(item => item.source_id)).size : node.sources}</b></div></div>
    <div className="confidence-row"><div><span className="eyebrow">REVIEW PRIORITY</span><span className="info-tip" tabIndex="0" aria-label="Review priority, not proof of identity"><Icon name="info" size={13}/><span className="tooltip-text">Review priority, not proof of identity.</span></span></div><span className={`status-pill ${apiEntity ? confidenceColor : color}`}><i/>{confidence}</span></div>
    <div className="related-row"><span className="eyebrow">RELATED TO</span>{relatedLinks.length ? relatedLinks.slice(0, 1).map(link => { const relatedId = link.from_entity_id === apiEntityId ? link.to_entity_id : link.from_entity_id; const related = caseData.entities.find(entity => entity.id === relatedId); return <button key={link.id} className="related-chip" onClick={() => setSelected(relatedId)}><span className="related-avatar"><Icon name="overview" size={13}/></span><span>{related?.display_label || relatedId}</span><span className="related-likelihood">{link.score >= .85 ? 'Strong lead' : link.score >= .4 ? 'Review' : 'Weak'}</span><Icon name="chevron" size={13}/></button>; }) : <span className="evidence-caption">No proposed link involving this entity</span>}</div>
    <div className="evidence-list-heading"><div><h3>Evidence items <span>({evidence.length})</span></h3><span className="evidence-caption">Signals supporting this record</span></div><button className="text-link" onClick={() => listRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>View all <Icon name="chevron" size={13}/></button></div>
    <div className="evidence-list" ref={listRef}>{evidence.map((item, i) => <article className="evidence-item" key={`${node.id}-${i}`}><div className={`evidence-item-icon ${i === 0 ? 'cyan' : i === 1 ? 'blue' : 'emerald'}`}><Icon name={item.icon} size={15}/></div><div className="evidence-item-main"><div className="evidence-item-title">{item.title}</div><div className="evidence-item-meta">{item.meta}</div></div><div className="evidence-item-end"><span className="evidence-score">{item.score}</span><span className={`mini-status ${item.status === 'Reviewed' ? 'reviewed' : item.status === 'Rejected' ? 'rejected' : 'needs-review'}`}>{item.status}</span></div></article>)}</div>
    {relatedLinks.length > 0 && <div className="review-links"><div className="eyebrow">LINK REVIEW &amp; TRACEABILITY</div>{relatedLinks.map(link => {
      const breakdown = link.score_breakdown || {};
      const dossier = link.dossier || breakdown.dossier || {};
      const hasConflicts = link.has_conflicts || dossier.has_conflicts;
      const si = dossier.source_independence;
      return <div className="review-link-row" key={link.id}>
        <div>
          <b>{link.id}</b>
          <span>{link.relation.replaceAll('_',' ')} · {(link.score * 100).toFixed(0)}% score · {link.review_status.replaceAll('_',' ')}</span>
          {hasConflicts && <small className="conflict-badge-mini">⚠️ Confirmed contradiction</small>}
          {si && <small className={`mini-ind-tag ${si.rating}`}>{si.rating.toUpperCase()} INDEPENDENCE</small>}
          {breakdown.caution && <small className="evidence-caption">{breakdown.caution}</small>}
          {breakdown.path_entity_ids && breakdown.path_entity_ids.length > 2 && <small className="mono">Path: {breakdown.path_entity_ids.map(id => caseData?.entities?.find(e => e.id === id)?.display_label || id).join(' → ')}</small>}
        </div>
        <div className="review-actions">
          <button disabled={reviewBusy === link.id || link.review_status === 'accepted'} onClick={() => onReviewLink(link.id, 'accepted')}>Accept</button>
          <button disabled={reviewBusy === link.id || link.review_status === 'rejected'} onClick={() => onReviewLink(link.id, 'rejected')}>Reject</button>
          <button disabled={reviewBusy === link.id || link.review_status === 'needs_more_evidence'} onClick={() => onReviewLink(link.id, 'needs_more_evidence')}>More evidence</button>
        </div>
      </div>;
    })}</div>}
    <div className="source-foot"><div className="source-icon"><Icon name="database" size={15}/></div><div><span className="eyebrow">SOURCE RELIABILITY</span><b>{apiEvidence.length ? new Set(apiEvidence.map(item => item.source_id)).size : 3} synthetic sources <span className="reliability-bars"><i/><i/><i/></span></b></div><span className="source-grade">{apiEntity ? sourceGrade : 'HIGH'}</span></div>
    <div className="review-note"><span className="review-note-icon"><Icon name="info" size={14}/></span><span>Links are investigative leads for analyst review, not proof of identity.</span></div>
  </motion.aside>;
}

const timelineExplanations = {
  profile_created: ['A new marketplace profile appeared in the archived records.', 'A new handle is a useful starting point, but creating a profile alone does not connect it to another account.'],
  signoff_observed: ['The post contains a sign-off phrase that can be compared with other archived posts.', 'A repeated phrase may support a writing-style lead. Common phrases can be copied, so it needs other evidence.'],
  wallet_observed: ['A payment instruction refers to a wallet recorded in this synthetic case.', 'A shared wallet can be a stronger link between accounts, but the record still needs source verification and analyst review.'],
  writing_and_activity: ['The post combines writing cues with an activity-time pattern.', 'These are broad behavioural signals. Similar schedules or wording do not establish that two accounts share an operator.'],
  infrastructure_observed: ['An archived service record exposed infrastructure details such as a banner, certificate, or reserved example IP.', 'Misconfiguration clues can point toward infrastructure relationships. They do not by themselves identify the person operating a service.'],
  certificate_confirmed: ['A second synthetic record matches a certificate reference from the service observation.', 'The matching certificate is a technical connection worth checking against the original records; it is not proof of who controlled the server.'],
  boilerplate_observed: ['A post repeats a phrase identified as a public template.', 'Because the wording is generic, this clue is weak on its own and should not drive attribution.'],
  closure_notice: ['The account posted that it was closing or moving on.', 'This provides a timeline marker for a possible account change. It does not show where the operator went next.'],
  account_inactive: ['An archived snapshot shows the account as inactive.', 'Inactivity can help establish timing, but it does not prove migration or rebranding.'],
  style_similarity: ['The post shares a writing feature associated with another persona in the synthetic archive.', 'Writing similarity is a lead only. Short or common phrases can create false matches, so look for independent identifiers.'],
  activity_pattern: ['Several posts fall within a recurring time window.', 'Activity timing may help compare accounts, but many people share similar schedules. It needs corroboration.'],
  impersonation_claim: ['The profile itself claims a connection to another handle.', 'A self-claim is not independent verification. Check identifiers and source context before treating it as a real relationship.'],
  analyst_context_note: ['An analyst note records a timing coincidence and explicitly states that no shared identifier was found.', 'Treat this as context for follow-up, not a proposed identity match. The missing shared identifier is a significant limitation.'],
};

function Timeline({ selectedMilestone, setSelectedMilestone, timeline = [], onOpenTimeline, caseData }) {
  const [range, setRange] = useState('Full range');
  const [hoveredEvent, setHoveredEvent] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const allMilestones = timeline.length ? timeline.map((item, index) => ({ ...item, date: item.observed_at.slice(0, 10), label: item.evidence_type.replaceAll('_', ' '), color: ['cyan', 'amber', 'emerald', 'muted'][index % 4], node: item.entity_id })) : milestones;
  const latest = new Date(`${allMilestones.at(-1)?.date || '2026-06-02'}T23:59:59`);
  const days = range === 'Last 30 days' ? 30 : range === 'Last 90 days' ? 90 : null;
  const cutoff = days ? new Date(latest.getTime() - days * 86400000) : null;
  const displayedMilestones = cutoff ? allMilestones.filter(item => new Date(`${item.date}T00:00:00`) >= cutoff) : allMilestones;
  const firstDate = displayedMilestones[0]?.date || '—';
  const lastDate = displayedMilestones.at(-1)?.date || '—';
  const activeEvent = hoveredEvent || selectedEvent;
  const explanation = activeEvent ? timelineExplanations[activeEvent.evidence_type] || ['This observation adds a timestamped clue to the case record.', 'Use it alongside independent evidence. A timeline entry is not proof of identity.'] : null;
  const linkedCandidates = activeEvent ? (caseData?.links || []).filter(link => link.evidence_ids?.includes(activeEvent.id)) : [];
  return <motion.section id="timeline" onMouseLeave={() => setHoveredEvent(null)} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5, delay: .34 }} className="timeline-card panel"><div className="timeline-header"><div><div className="eyebrow">OBSERVATION HISTORY</div><h2><span className="heading-orb timeline-icon"><Icon name="timeline" size={16}/></span>Timeline</h2></div><div className="timeline-controls"><span className="timeline-range mono">{firstDate} <i>→</i> {lastDate}</span><label className="range-select"><select value={range} onChange={e => setRange(e.target.value)} aria-label="Timeline range"><option>Full range</option><option>Last 90 days</option><option>Last 30 days</option></select><span>⌄</span></label></div></div>
    <div className="timeline-scroll"><div className="timeline-track" style={{ minWidth: `${Math.max(760, displayedMilestones.length * 145)}px` }}><div className="timeline-line"/><div className="timeline-fill"/>{displayedMilestones.map((m, i) => <button key={`${m.date}-${i}`} className={`milestone ${m.color} ${selectedMilestone === m.node || selectedEvent?.id === m.id ? 'milestone-active' : ''}`} style={{ left: `${displayedMilestones.length < 2 ? 2 : i * (90 / (displayedMilestones.length - 1)) + 2}%` }} onMouseEnter={() => m.id && setHoveredEvent(m)} onFocus={() => m.id && setHoveredEvent(m)} onClick={() => { setSelectedMilestone(m.node); if (m.id) setSelectedEvent(m); }} aria-expanded={activeEvent?.id === m.id} aria-label={`${m.date}: ${m.label}. Hover or select for explanation.`}><span className="milestone-dot"/><span className="milestone-date mono">{m.date}</span><span className="milestone-label">{m.label}</span>{m.status && <span className={`milestone-status ${m.status === 'Reviewed' ? 'reviewed' : 'needs-review'}`}>{m.status}</span>}</button>)}</div></div>
    {activeEvent && <section className="timeline-explanation" aria-live="polite"><div className="timeline-explain-icon"><Icon name="info" size={16}/></div><div className="timeline-explain-copy"><div className="eyebrow">OBSERVATION EXPLAINED · {activeEvent.date}</div><h3>{activeEvent.entity_label ? `${activeEvent.entity_label} · ` : ''}{activeEvent.evidence_type?.replaceAll('_', ' ') || activeEvent.label}</h3><p className="timeline-observation-summary">{activeEvent.summary || activeEvent.label}</p><p>{explanation[0]} {explanation[1]}</p><div className="timeline-explain-meta">{activeEvent.source_name && <span>Source: <b>{activeEvent.source_name}</b>{activeEvent.source_reliability != null ? ` · reliability ${(activeEvent.source_reliability * 100).toFixed(0)}%` : ''}</span>}{activeEvent.confidence != null && <span>Signal confidence: <b>{(activeEvent.confidence * 100).toFixed(0)}%</b></span>}{activeEvent.entity_label && <span>Record: <b>{activeEvent.entity_label}</b></span>}</div>{linkedCandidates.length > 0 && <div className="timeline-linked-lead"><b>Used in {linkedCandidates.length} candidate link{linkedCandidates.length > 1 ? 's' : ''}</b><span>{linkedCandidates.map(link => `${link.id} · ${(link.score * 100).toFixed(0)}% review score`).join('  |  ')}. Scores prioritize analyst review; they are not probabilities of identity.</span></div>}<div className="timeline-caution"><Icon name="info" size={13}/> Synthetic clue for analyst review only. This observation does not prove who operated an account or service.</div></div><button className="timeline-explain-close" onClick={() => { setSelectedEvent(null); setHoveredEvent(null); }} aria-label="Close timeline explanation"><Icon name="close" size={14}/></button></section>}
    <div className="timeline-foot"><span><i className="footer-live-dot"/> {displayedMilestones.length} observations <b>·</b> Synthetic archive</span><button className="text-link" onClick={onOpenTimeline}>Open full timeline <Icon name="chevron" size={13}/></button></div>
  </motion.section>;
}

function WorkspaceDialog({ panel, onClose, caseData, caseId, query, setQuery, saved, setSaved, showEvidenceEdges, setShowEvidenceEdges, refreshCase, onReviewLink, reviewBusy, reviewError, runAnalysis, analysisBusy, analysisResult, analysisError, onImportCase, importBusy, importError, clearImportError }) {
  const [queueFilter, setQueueFilter] = useState('pending');
  const [showAuditHistory, setShowAuditHistory] = useState(false);
  const [importBundle, setImportBundle] = useState(null);
  const [importFileName, setImportFileName] = useState('');
  const [fileError, setFileError] = useState('');
  const [previewData, setPreviewData] = useState(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  useEffect(() => { setQueueFilter('pending'); setShowAuditHistory(false); setPreviewData(null); }, [caseId]);
  if (!panel) return null;
  const saveSearch = () => {
    const term = query.trim(); if (!term || saved.some(item => item.query === term)) return;
    const next = [...saved, { id: `${Date.now()}`, query: term }]; setSaved(next); localStorage.setItem('darklens-saved-searches', JSON.stringify(next));
  };
  const removeSearch = id => { const next = saved.filter(item => item.id !== id); setSaved(next); localStorage.setItem('darklens-saved-searches', JSON.stringify(next)); };
  const rows = caseData?.entities || [];
  const evidence = caseData?.evidence || [];
  const links = caseData?.links || [];
  const evidenceById = new Map(evidence.map(item => [item.id, item]));
  const entityById = new Map(rows.map(item => [item.id, item]));
  const sourceById = new Map((caseData?.sources || []).map(item => [item.id, item]));
  const filteredLinks = links.filter(link => queueFilter === 'all' || (queueFilter === 'pending' ? ['unreviewed','needs_more_evidence'].includes(link.review_status) : queueFilter === 'more' ? link.review_status === 'needs_more_evidence' : link.review_status === queueFilter));
  return <div className="dialog-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><section className={`workspace-dialog panel ${panel === 'Review Queue' ? 'review-queue-dialog' : ''}`} role="dialog" aria-modal="true" aria-label={panel}>
    <div className="dialog-header"><div><span className="eyebrow">{caseData?.case?.id || caseId || CASE_ID} · SYNTHETIC WORKSPACE</span><h2>{panel}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close dialog"><Icon name="close" size={16}/></button></div>
    {panel === 'Reports' && <div className="dialog-content"><p>Export the current synthetic case records for review or include the case in a printable handoff.</p><div className="export-options"><a href={exportCase(caseId,'report')} download>Download analyst report · Markdown</a><a href={exportCase(caseId,'json')} download>Download full case · JSON</a><a href={exportCase(caseId,'csv','entities')} download>Download entities · CSV</a><a href={exportCase(caseId,'csv','evidence')} download>Download evidence · CSV</a><a href={exportCase(caseId,'csv','links')} download>Download candidate links · CSV</a><a href={exportCase(caseId,'csv','audit')} download>Download audit history · CSV</a><button onClick={() => window.print()}>Print current case report</button></div><div className="dialog-summary">{rows.length} entities · {links.length} candidate links · {evidence.length} items · {caseData?.audit_events?.length || 0} audit events</div></div>}
    {panel === 'Import JSON' && <div className="dialog-content import-content"><p>Import a version 1.0 synthetic case bundle. DarkLens validates the file, creates the case records, then adds any matching links to the review queue.</p><div className="import-safety-note"><b>Synthetic records only</b><span>Imported links are review leads; none are accepted automatically. Reused record IDs are automatically namespaced per case. DarkLens never silently overwrites an existing case.</span></div><label className="import-file-label">Choose JSON bundle<input type="file" accept="application/json,.json" onChange={async event => { clearImportError?.(); setFileError(''); setImportBundle(null); setImportFileName(''); setPreviewData(null); const file = event.target.files?.[0]; if (!file) return; if (file.size > 5 * 1024 * 1024) { setFileError('File is larger than the 5 MB import limit.'); return; } try { const parsed = JSON.parse(await file.text()); setImportBundle(parsed); setImportFileName(file.name); setPreviewBusy(true); previewCaseBundle(parsed).then(prev => setPreviewData(prev)).catch(err => { setFileError(err.message); setImportBundle(null); }).finally(() => setPreviewBusy(false)); } catch { setFileError('This file is not valid JSON.'); setImportBundle(null); } }}/></label>{fileError && <div className="review-error" role="alert">{fileError}</div>}{importError && <div className="review-error import-error" role="alert">{importError}</div>}{previewBusy && <div className="api-notice" role="status">Validating synthetic case structure and schema…</div>}{previewData && <div className="import-preview"><b>{previewData.case_title} <small className="mono">({previewData.case_id})</small></b><span>{importFileName} · {previewData.counts.entities} entities · {previewData.counts.sources} sources · {previewData.counts.observations} observations</span>{previewData.entity_types && <small className="import-types">Record types: {Object.entries(previewData.entity_types).map(([t, count]) => `${count} ${t.replaceAll('_', ' ')}`).join(' · ')}</small>}{previewData.warning ? <div className="review-error" role="alert">{previewData.warning}</div> : <small className="good-text">✓ Valid bundle format. Ready to import as an isolated synthetic case.</small>}</div>}<button className="dialog-primary" disabled={!importBundle || !previewData || Boolean(fileError) || importBusy || previewBusy || Boolean(previewData?.case_exists)} onClick={() => onImportCase(importBundle)}>{importBusy ? 'Importing synthetic case…' : 'Confirm and import case'}</button><a className="import-template-link" href="/hollowreed_case.json" download>Download prepared Hollowreed synthetic case</a><a className="import-template-link" href="/case_bundle_v1.template.json" download>Download JSON format example</a><div className="dialog-summary">Required sections: schema_version, data_mode, case, sources, entities, observations. Do not include links.</div></div>}
    {panel === 'Review Queue' && <div className="dialog-content review-queue-content"><div className="review-queue-intro"><p>Review attribution candidates separately from graph-only evidence associations. Each candidate shows its supporting records and score inputs; your decision is saved to the case audit history.</p><button className="dialog-primary analyze-button" onClick={runAnalysis} disabled={analysisBusy}>{analysisBusy ? 'Analyzing synthetic records…' : 'Run case analysis'}</button></div>
      {reviewError && <div className="review-error" role="alert">{reviewError}</div>}{analysisError && <div className="review-error" role="alert">{analysisError}</div>}
      <div className="queue-view-tabs" role="tablist" aria-label="Review queue views"><button role="tab" aria-selected={!showAuditHistory} className={!showAuditHistory ? 'selected' : ''} onClick={() => setShowAuditHistory(false)}>Candidate review</button><button role="tab" aria-selected={showAuditHistory} className={showAuditHistory ? 'selected' : ''} onClick={() => setShowAuditHistory(true)}>Audit history <span>{caseData?.audit_events?.length || 0}</span></button></div>
      {showAuditHistory ? <section className="audit-history" aria-label="Analyst audit history">{caseData?.audit_events?.length ? caseData.audit_events.map(event => <article className="audit-event" key={event.id}><div className="audit-event-marker"><Icon name="evidence" size={14}/></div><div className="audit-event-body"><div><b>{event.target_id}</b><span>{event.action.replace('review_status:','').replaceAll('_',' ')}</span></div><p>{event.note || 'No analyst note recorded.'}</p><small>{event.actor_label} · {new Date(event.timestamp).toLocaleString()}</small></div></article>) : <div className="dialog-empty">No review actions have been recorded for this case yet. Decisions made in the queue will appear here.</div>}</section> : <>
      <div className="queue-filter-row" role="group" aria-label="Filter review queue">{[['pending','Pending'],['all','All'],['accepted','Accepted'],['rejected','Rejected'],['more','More evidence']].map(([value,label]) => <button key={value} className={queueFilter === value ? 'selected' : ''} onClick={() => setQueueFilter(value)}>{label}</button>)}</div>
      <div className="review-queue-list">{filteredLinks.map(link => {
        const from = entityById.get(link.from_entity_id);
        const to = entityById.get(link.to_entity_id);
        const breakdown = link.score_breakdown || {};
        const dossier = link.dossier || breakdown.dossier || {};
        const hasConflicts = link.has_conflicts || dossier.has_conflicts;
        const hasInconsistencies = dossier.has_inconsistencies;
        const signals = breakdown.signals || [];
        const supporting = dossier.supporting_evidence || [];
        const counter = dossier.counter_evidence || [];
        const grouped = dossier.grouped_evidence || [];
        const sourceInd = dossier.source_independence || {};
        const weak = dossier.weak_or_missing_evidence || [];

        return <article className="queue-card" key={link.id}>
          {hasConflicts ? (
            <div className="queue-conflict-banner confirmed" role="alert">
              <div className="conflict-tag-title"><Icon name="close" size={13}/> <b>Confirmed Contradiction</b></div>
              <p>{dossier.conflict_summary || 'An observation in this case explicitly refutes or contradicts common control.'}</p>
            </div>
          ) : hasInconsistencies ? (
            <div className="queue-conflict-banner inconsistency" role="status">
              <div className="conflict-tag-title"><Icon name="info" size={13}/> <b>Review Context / Inconsistency</b></div>
              <p>{dossier.conflict_summary || 'Potential timing overlap or shared infrastructure requires analyst scrutiny.'}</p>
            </div>
          ) : null}
          <div className="queue-card-heading">
            <div>
              <span className="queue-id">{link.id}</span>
              <h3>{from?.display_label || link.from_entity_id}<span> ↔ </span>{to?.display_label || link.to_entity_id}</h3>
              <p>{link.relation.replaceAll('_',' ')}</p>
            </div>
            <div className="queue-score">
              <b>{Math.round(link.score * 100)}</b>
              <span>review priority</span>
            </div>
          </div>
          <div className="queue-state-row">
            <span className={`status-chip ${link.review_status === 'accepted' ? 'reviewed' : link.review_status === 'rejected' ? 'rejected' : 'needs-review'}`}>
              {link.review_status.replaceAll('_',' ')}
            </span>
            <span className={`priority-tag ${link.priority}`}>
              {link.priority.replaceAll('_',' ')}
            </span>
            {hasConflicts && <span className="conflict-badge-mini">Contradiction</span>}
          </div>
          {sourceInd.rating && (
            <div className="queue-independence-row">
              <span className={`independence-tag ${sourceInd.rating}`}>{sourceInd.rating.toUpperCase()} INDEPENDENCE</span>
              <small>{sourceInd.description}</small>
            </div>
          )}
          {breakdown.path_entity_ids && breakdown.path_entity_ids.length > 2 && (
            <div className="queue-path-badge">
              <small>Inference path: </small>
              <span className="mono">{breakdown.path_entity_ids.map(id => entityById.get(id)?.display_label || id).join(' → ')}</span>
            </div>
          )}
          {supporting.length > 0 ? (
            <details className="queue-dossier-details" open>
              <summary>Supporting evidence provenance ({supporting.length})</summary>
              <div className="dossier-items">
                {supporting.map(item => (
                  <div className="dossier-row" key={item.observation_id}>
                    <span className="mono">{item.observation_id}</span>
                    <div>
                      <strong>{item.summary}</strong>
                      <small>
                        Source: <b>{item.source_name}</b> ({Math.round(item.source_reliability * 100)}% rel) ·
                        Confidence: <b>{Math.round(item.confidence * 100)}%</b> ·
                        Match: <b>{Math.round(item.match_strength * 100)}%</b> ·
                        Contribution: <b>+{item.contribution.toFixed(2)}</b>
                      </small>
                    </div>
                  </div>
                ))}
              </div>
            </details>
          ) : (
            <div className="queue-evidence">
              <b>Evidence trail · {link.evidence_ids.length}</b>
              {link.evidence_ids.map(id => {
                const item = evidenceById.get(id);
                if (!item) return null;
                const source = sourceById.get(item.source_id);
                return <div className="queue-evidence-row" key={id}>
                  <span className="mono">{id}</span>
                  <div>
                    <strong>{item.summary}</strong>
                    <small>{source?.name || 'Unknown source'} · reliability {Math.round((source?.reliability || 0) * 100)}% · signal {Math.round(item.confidence * 100)}% · {item.observed_at?.slice(0,10)}</small>
                  </div>
                </div>;
              })}
            </div>
          )}
          {counter.length > 0 && (
            <div className="queue-counter-card">
              <div className="counter-card-header">
                <Icon name="info" size={14}/>
                <b>Counter-Evidence &amp; Inconsistencies ({counter.length})</b>
              </div>
              {counter.map((c, ci) => (
                <div className={`counter-row ${c.is_confirmed_contradiction ? 'confirmed-row' : 'inconsistent-row'}`} key={`${c.observation_id}-${ci}`}>
                  <div className="counter-row-tag">{c.is_confirmed_contradiction ? 'CONFIRMED CONTRADICTION' : 'REVIEW CONTEXT'}</div>
                  <div className="counter-row-content">
                    <strong>{c.summary}</strong>
                    <small>{c.explanation}</small>
                  </div>
                </div>
              ))}
            </div>
          )}
          {grouped.length > 0 && (
            <details className="queue-grouped-details">
              <summary>Grouped duplicate / dependent clues ({grouped.length}) · discounted to prevent inflation</summary>
              <div className="grouped-items">
                {grouped.map((g, gi) => (
                  <div className="grouped-row" key={`${g.observation_id}-${gi}`}>
                    <span className="mono">{g.observation_id}</span>
                    <div>
                      <strong>{g.summary}</strong>
                      <small className="discount-reason">{g.reason}</small>
                    </div>
                  </div>
                ))}
              </div>
            </details>
          )}
          {weak.length > 0 && (
            <div className="queue-weakness-list">
              {weak.map((w, wi) => (
                <span key={wi} className="weakness-item"><Icon name="info" size={12}/> {w}</span>
              ))}
            </div>
          )}
          {signals.length > 0 && (
            <details className="queue-signals">
              <summary>Why this score · {signals.length} signal{signals.length === 1 ? '' : 's'}</summary>
              <div>
                {signals.map((signal, index) => (
                  <span key={`${signal.signal}-${index}`}>
                    {signal.signal.replaceAll('_',' ')}: {Math.round(signal.match * 100)}% match × {Math.round(signal.source_reliability * 100)}% source reliability
                    {signal.evidence_confidence != null ? ` · record confidence ${Math.round(signal.evidence_confidence * 100)}%` : ''}
                    {signal.contribution != null ? ` · contribution ${Math.round(signal.contribution * 100)}%` : ''}
                  </span>
                ))}
              </div>
            </details>
          )}
          {breakdown.score_explanation && <p className="queue-score-note">{breakdown.score_explanation}</p>}
          {breakdown.caution && <p className="queue-caution">{breakdown.caution}</p>}
          <p className="queue-score-note">Scores prioritize review. They are not probabilities of identity.</p>
          <div className="review-actions">
            <button disabled={reviewBusy === link.id || link.review_status === 'accepted'} onClick={() => onReviewLink(link.id, 'accepted')}>{reviewBusy === link.id ? 'Saving…' : 'Accept lead'}</button>
            <button disabled={reviewBusy === link.id || link.review_status === 'rejected'} onClick={() => onReviewLink(link.id, 'rejected')}>Reject lead</button>
            <button disabled={reviewBusy === link.id || link.review_status === 'needs_more_evidence'} onClick={() => onReviewLink(link.id, 'needs_more_evidence')}>Request more evidence</button>
          </div>
        </article>;
      })}{filteredLinks.length === 0 && <div className="dialog-empty">No links match this filter.</div>}</div>
      {analysisResult && <section className="analysis-results"><div className="queue-section-heading"><div><span className="eyebrow">SYNTHETIC CASE ANALYSIS</span><h3>{analysisResult.suggestion_count} attribution leads · {analysisResult.evidence_associations?.length || 0} evidence associations · {analysisResult.behavioral_leads?.length || 0} weak pattern leads</h3></div><span className="synthetic-mini"><i/>Synthetic only</span></div><p>{analysisResult.method}. Added {analysisResult.added_count || 0} new leads to this case’s review queue; none were accepted automatically.</p>{analysisResult.suggestions.map(item => <div className="analysis-suggestion" key={`${item.from_entity_id}-${item.to_entity_id}`}><div><b>{item.from_label} ↔ {item.to_label}</b><small>{item.relation.replaceAll('_',' ')} · evidence {item.evidence_ids.join(', ')}</small></div><span>{Math.round(item.score * 100)}<small>review</small></span></div>)}{analysisResult.evidence_associations?.length > 0 && <details className="analysis-limitations"><summary>Evidence associations · not attribution candidates</summary><div className="association-list">{analysisResult.evidence_associations.map((item,index) => <p key={`${item.from_entity_id}-${item.to_entity_id}-${index}`}><b>{item.from_label} ↔ {item.to_label}</b><span>{item.signals.map(signal => signal.signal.replaceAll('_',' ')).join(', ')} · evidence {item.evidence_ids.join(', ')}</span></p>)}</div><small>These edges show which records are connected by cited evidence. They are kept out of the attribution review queue unless a separate analysis method supports a lead.</small></details>}{analysisResult.behavioral_leads?.length > 0 ? <div className="behavioral-leads"><b>Weak style/activity leads · analyst review required</b>{analysisResult.behavioral_leads.map(item => <div className="analysis-suggestion" key={`activity-${item.from_entity_id}-${item.to_entity_id}`}><div><b>{item.from_label} ↔ {item.to_label}</b><small>{item.sample_counts ? `${item.sample_counts[item.from_entity_id]} + ${item.sample_counts[item.to_entity_id]} activity observations · ` : ''}evidence {item.evidence_ids.join(', ')}</small><small className="behavioral-caution">{item.caution} Review priority is capped at 45%.</small></div><span>{Math.round(item.score * 100)}<small>review</small></span></div>)}</div> : <p className="analysis-empty-note">No weak activity or style lead met the current minimum rules for this case.</p>}<details className="analysis-limitations"><summary>Method and limitations</summary><ul>{analysisResult.limitations.map(item => <li key={item}>{item}</li>)}</ul></details></section>}
      </>}
      <div className="dialog-summary">Analyst decisions are saved with timestamps and notes. No link is auto-accepted.</div>
    </div>}
    {panel === 'Saved Searches' && <div className="dialog-content"><p>Save a search phrase and reopen it against the current case records.</p><div className="save-search-row"><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search handles, keys, wallets, or IDs"/><button onClick={saveSearch} disabled={!query.trim()}>Save search</button></div>{saved.length ? <div className="saved-search-list">{saved.map(item => <div key={item.id}><button className="saved-query" onClick={() => { setQuery(item.query); onClose(); }}>{item.query}</button><button className="remove-saved" onClick={() => removeSearch(item.id)} aria-label={`Remove ${item.query}`}>×</button></div>)}</div> : <div className="dialog-empty">No saved searches yet.</div>}</div>}
    {panel === 'Settings' && <div className="dialog-content"><p>These settings apply to this local synthetic investigation workspace.</p><label className="setting-toggle"><span><b>Show evidence association edges</b><small>Display links inferred from evidence records in the graph.</small></span><input type="checkbox" checked={showEvidenceEdges} onChange={event => setShowEvidenceEdges(event.target.checked)}/></label><div className="setting-info"><b>Data mode</b><span>Synthetic archive only · no live collection</span><b>Case service</b><span>Local API · {caseId}</span></div><button className="dialog-primary" onClick={refreshCase}>Refresh case records</button></div>}
  </section></div>;
}

export default function App() {
  const [active, setActive] = useState('Case Overview');
  const [selected, setSelected] = useState(null);
  const [selectedMilestone, setSelectedMilestone] = useState(null);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [caseData, setCaseData] = useState(null);
  const [cases, setCases] = useState([]);
  const [currentCaseId, setCurrentCaseId] = useState(CASE_ID);
  const [timelineData, setTimelineData] = useState([]);
  const [panel, setPanel] = useState(null);
  const [query, setQuery] = useState('');
  const [reviewBusy, setReviewBusy] = useState('');
  const [reviewError, setReviewError] = useState('');
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [analysisError, setAnalysisError] = useState('');
  const [analysisResult, setAnalysisResult] = useState(null);
  const [importBusy, setImportBusy] = useState(false);
  const [importError, setImportError] = useState('');
  const [showEvidenceEdges, setShowEvidenceEdges] = useState(true);
  const [saved, setSaved] = useState(() => { try { return JSON.parse(localStorage.getItem('darklens-saved-searches') || '[]'); } catch { return []; } });
  const [apiError, setApiError] = useState('');
  const [loading, setLoading] = useState(true);
  const mainRef = useRef(null);
  const loadCase = (caseId = currentCaseId) => Promise.all([getCase(caseId), getTimeline(caseId)]).then(([payload, timeline]) => { setCurrentCaseId(caseId); localStorage.setItem('darklens-active-case', caseId); setCaseData(payload); setTimelineData(timeline); setApiError(''); setLoading(false); return payload; }).catch(error => { setApiError(error.message || 'Could not connect to the DarkLens API.'); setLoading(false); throw error; });
  useEffect(() => {
    let cancelled = false;
    getCases()
      .then(items => { if (cancelled) return null; setCases(items); const preferred = localStorage.getItem('darklens-active-case'); const initial = items.find(item => item.id === preferred) || items[0]; if (!initial) throw new Error('No cases are available in the local workspace.'); setCurrentCaseId(initial.id); return Promise.all([getCase(initial.id), getTimeline(initial.id)]).then(result => ({ result, id: initial.id })); })
      .then(data => { if (!cancelled && data) { const [payload, timeline] = data.result; setCaseData(payload); setTimelineData(timeline); localStorage.setItem('darklens-active-case', data.id); setApiError(''); setSelected(payload.entities[0]?.id || null); } })
      .catch(error => { if (!cancelled) setApiError(error.message || 'Could not connect to the DarkLens API.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);
  const selectCase = caseId => { setLoading(true); setSelectedMilestone(null); setAnalysisResult(null); setSelected(null); loadCase(caseId).then(payload => setSelected(payload.entities[0]?.id || null)).catch(() => {}); };
  const handleImportCase = async bundle => {
    setImportBusy(true); setImportError('');
    try {
      const imported = await importCaseBundle(bundle);
      const items = await getCases(); setCases(items);
      const payload = await loadCase(imported.case.id);
      setPanel(null); setActive('Case Overview'); setSelected(payload.entities[0]?.id || null);
    } catch (error) { setImportError(error.message || 'Could not import this synthetic case.'); }
    finally { setImportBusy(false); }
  };
  const navigate = destination => {
    setActive(destination); setMobileOpen(false);
    if (['Reports','Saved Searches','Settings','Review Queue'].includes(destination)) { setPanel(destination); return; }
    const target = destination === 'Actor Graph' ? 'graph' : destination === 'Evidence' ? 'evidence' : destination === 'Timeline' ? 'timeline' : 'overview';
    requestAnimationFrame(() => document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: target === 'overview' ? 'start' : 'center' }));
  };
  const handleReview = async (linkId, status) => {
    setReviewBusy(linkId); setReviewError('');
    try { await reviewLink(linkId, status, `Reviewed in DarkLens case ${currentCaseId} UI`); await loadCase(); }
    catch (error) { setReviewError(error.message || 'Could not save analyst review.'); }
    finally { setReviewBusy(''); }
  };
  const runSyntheticAnalysis = async () => {
    setAnalysisBusy(true); setAnalysisError('');
    try {
      const result = await saveAnalysis(currentCaseId);
      await loadCase(currentCaseId);
      setAnalysisResult({ ...result.analysis, added_count: result.added_count });
    }
    catch (error) { setAnalysisError(error.message || 'Could not analyze synthetic records.'); }
    finally { setAnalysisBusy(false); }
  };
  useEffect(() => {
    if (!selectedMilestone) return;
    setSelected(selectedMilestone);
  }, [selectedMilestone]);
  const reviewTotal = caseData?.links.length || 0;
  const reviewedCount = caseData?.links.filter(link => link.review_status === 'accepted').length || 0;
  const rejectedCount = caseData?.links.filter(link => link.review_status === 'rejected').length || 0;
  const pendingCount = Math.max(0, reviewTotal - reviewedCount - rejectedCount);
  const progress = reviewTotal ? Math.round(reviewedCount / reviewTotal * 100) : 0;
  return <div className="app-shell">
    <div className="ambient ambient-one"/><div className="ambient ambient-two"/><div className="particle particle-one"/><div className="particle particle-two"/><div className="particle particle-three"/>
    <Sidebar active={active} setActive={navigate} collapsed={collapsed} setCollapsed={setCollapsed} mobileOpen={mobileOpen} evidenceCount={caseData?.evidence.length || 0} pendingCount={pendingCount}/>
    {mobileOpen && <button className="mobile-scrim" onClick={() => setMobileOpen(false)} aria-label="Close navigation"/>}
    <div className="main-column" ref={mainRef}>
      <div className="mobile-header"><button className="icon-button" onClick={() => setMobileOpen(!mobileOpen)} aria-label="Open navigation"><Icon name="menu"/></button><Logo/><span className="synthetic-pill"><span/>Synthetic data</span></div>
      <Topbar setActive={navigate} caseTitle={caseData?.case.id || currentCaseId} cases={cases} query={query} setQuery={setQuery} entities={caseData?.entities || []} onSelectEntity={setSelected} onSelectCase={selectCase} openPanel={setPanel}/>
      <main className="main-content">
        {apiError && <div className="api-notice" role="status"><b>API unavailable:</b> {apiError}. Start the local backend to load case records. Displaying the built-in synthetic preview.</div>}
        {!apiError && loading && <div className="api-notice" role="status">Connecting to the local synthetic case service…</div>}
        <div id="overview" className="page-title-row enter"><div><div className="breadcrumbs"><span>Workspace</span><Icon name="chevron" size={12}/><span>Cases</span><Icon name="chevron" size={12}/><b>{caseData?.case.id || currentCaseId}</b></div><h1>Case Overview <span className="case-number mono">{caseData?.case.id || currentCaseId}</span></h1><p>{caseData?.case.title || 'Evidence-backed leads for analyst review'} <span className="title-separator">/</span> <span className="synthetic-inline"><i/> Synthetic case</span></p></div><button className="export-button" onClick={() => setPanel('Reports')}><Icon name="evidence" size={15}/>Export case</button></div>
        <div className="stats-grid">
          <StatCard icon="case" eyebrow="ACTIVE CASE" title={caseData?.case.title || 'Nightjar'} accent="cyan" delay={40}><span className="mono">{caseData?.case.id || currentCaseId}</span><span className="stat-dot-separator">·</span><span className="synthetic-mini"><i/>Synthetic data</span></StatCard>
          <StatCard icon="users" eyebrow="TRACKED ENTITIES" title="Entities" accent="blue" delay={90} count={caseData?.entities.length || 0}><span>{caseData?.entities.filter(entity => entity.type === 'persona').length || 0} personas</span><span className="stat-dot-separator">·</span><span>{caseData?.entities.filter(entity => ['handle', 'pgp_key', 'wallet'].includes(entity.type)).length || 0} identifiers</span></StatCard>
          <StatCard icon="database" eyebrow="PROPOSED LINKS" title="Candidate links" accent="emerald" delay={140} count={reviewTotal}><span className="good-text">{reviewedCount} accepted</span><span className="stat-dot-separator">·</span><span className="warn-text">{pendingCount} pending · {rejectedCount} rejected</span></StatCard>
          <StatCard icon="alert" eyebrow="REVIEW PROGRESS" title="Analyst review" accent="amber" delay={190} ring={progress}><span>{reviewedCount} of {reviewTotal} links accepted</span></StatCard>
        </div>
        {reviewError && <div className="review-error" role="alert">{reviewError}</div>}
        <div className="workspace-grid"><ActorGraph selected={selected} setSelected={setSelected} activeMilestone={selectedMilestone} caseData={caseData} showEvidenceEdges={showEvidenceEdges}/><EvidencePanel selected={selected} setSelected={setSelected} caseData={caseData} onReviewLink={handleReview} reviewBusy={reviewBusy}/></div>
        <Timeline selectedMilestone={selectedMilestone} setSelectedMilestone={setSelectedMilestone} timeline={timelineData} caseData={caseData} onOpenTimeline={() => navigate('Timeline')}/>
        <footer className="page-footer"><span><Logo/><span className="footer-copy">© 2024 DarkLens Intelligence Workspace</span></span><span className="footer-right"><i className="system-pulse"/> Synthetic environment <span className="footer-divider"/> Data is illustrative and generated for demonstration</span></footer>
      </main>
    </div>
    <WorkspaceDialog panel={panel} onClose={() => { setPanel(null); setActive('Case Overview'); }} caseData={caseData} caseId={currentCaseId} query={query} setQuery={setQuery} saved={saved} setSaved={setSaved} showEvidenceEdges={showEvidenceEdges} setShowEvidenceEdges={setShowEvidenceEdges} refreshCase={() => loadCase()} onReviewLink={handleReview} reviewBusy={reviewBusy} reviewError={reviewError} runAnalysis={runSyntheticAnalysis} analysisBusy={analysisBusy} analysisResult={analysisResult} analysisError={analysisError} onImportCase={handleImportCase} importBusy={importBusy} importError={importError} clearImportError={() => setImportError('')}/>
  </div>;
}
