/* 0DTE dashboard — self-hosted port of the Muse streaming dashboard (3pacs/muse implementation/dashboard-streaming,
   client/src/App.tsx) as plain JS over the interpreter's own feeds. Same-origin: /feed/all + /feed/signals (this host),
   polled every 15 s while open. No inline script/style (site CSP). Pure view logic is exported for the Node test. */
(function (root) {
  'use strict';
  var POLL_MS = 15000, STALE_AFTER_MS = 120000, MAX_FUTURE_SKEW_MS = 120000, PT = 'America/Los_Angeles';
  var AWARE_TS_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})$/;
  var num = function (v) { return typeof v === 'number' && isFinite(v) ? v : null; };
  function fmt(n, d) { n = num(n); if (n === null) return '—'; if (d === undefined) d = 2; return n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }); }
  function fmtInt(n) { n = num(n); return n === null ? '—' : Math.round(n).toLocaleString('en-US'); }
  function fmtMoneyM(n) { n = num(n); if (n === null) return '—'; return (n < 0 ? '−' : '') + '$' + Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 }) + 'M'; }
  function fmtTime(iso) { if (!iso) return '—'; var d = new Date(iso); if (isNaN(d.getTime())) return '—'; return new Intl.DateTimeFormat('en-US', { timeZone: PT, hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true }).format(d); }
  function fmtTimeShort(iso) { var d = new Date(iso); if (isNaN(d.getTime())) return ''; return new Intl.DateTimeFormat('en-US', { timeZone: PT, hour: '2-digit', minute: '2-digit', hour12: false }).format(d); }
  function ageLabel(iso, nowMs) { if (!iso) return ''; var t = new Date(iso).getTime(); if (isNaN(t)) return ''; var s = Math.max(0, Math.round((nowMs - t) / 1000)); if (s < 60) return s + 's ago'; var m = Math.floor(s / 60); if (m < 60) return m + 'm ago'; return Math.floor(m / 60) + 'h ' + (m % 60) + 'm ago'; }
  function fmtEtTime(ts) { if (!ts) return '—'; var m = /(\d{1,2}:\d{2})/.exec(ts); return m ? m[1] : ts; }

  // ---- pure view logic (mirrors the React app's ADOPT-F1 helpers) ----
  function parseAwareMs(v) { if (typeof v !== 'string' || !AWARE_TS_RE.test(v)) return null; var ms = Date.parse(v); return isFinite(ms) ? ms : null; }
  function feedAgeMs(updatedAt, nowMs) { var ms = parseAwareMs(updatedAt); if (ms === null) return null; var age = nowMs - ms; if (age < -MAX_FUTURE_SKEW_MS) return null; return age < 0 ? 0 : age; }
  function computeStatus(a) {
    if (a.paused) return 'paused';
    if (!a.hasData || a.isError) return 'down';
    if (a.showingStale || !a.dataOk) return 'down';
    if (a.marketOpen === false) return 'closed';
    if (a.ageMs === null) return 'stale';
    if (a.ageMs > STALE_AFTER_MS) return 'stale';
    return 'live';
  }
  function clusterState(cluster, prints60m) {
    if (cluster === true) return { kind: 'clustering', text: prints60m !== null && prints60m !== undefined ? '⚠️ CLUSTERING (' + prints60m + ' in last hour)' : '⚠️ CLUSTERING (count unknown)' };
    if (cluster === false) return { kind: 'isolated', text: 'isolated' };
    return { kind: 'unknown', text: 'clustering unknown (legacy row)' };
  }
  // Normalise the interpreter's /feed/all into the flat shape the React client rendered (server getLive did this).
  function normalize(f) {
    if (!f || f.status !== 'ok') return null;
    var g = f.gamma || {}, p = f.positioning || {}, em = p.expected_move || {}, fl = f.flow || {}, iv = f.iv || {}, vc = f.vanna_charm || {}, src = f.sources || {};
    var by = (g.by_strike || []).map(function (s) { return { strike: num(s.strike), netGexM: num(s.net_gex_m), callGexM: num(s.call_gex_m), putGexM: num(s.put_gex_m), src: s.src || null }; }).filter(function (s) { return s.strike !== null; });
    var known = by.filter(function (s) { return s.netGexM !== null; }).length;
    return {
      status: f.status, updatedAt: f.updated_at, quoteAsOf: f.quote_as_of || null, marketOpen: !!f.market_open, spot: num(f.spot), expiry: f.expiry || null,
      netGexM: num(g.net_gex_m), gammaFlip: num(g.gamma_flip), callWall: num(g.call_wall), putWall: num(g.put_wall), maxPain: num(g.max_pain), regime: g.regime || null,
      pinScore: num(p.pin_score), pinMagnet: num(p.pin_magnet), pinComponents: p.pin_components ? { concentration: num(p.pin_components.concentration), proximity: num(p.pin_components.proximity), timeElapsed: num(p.pin_components.time_elapsed) } : null,
      expectedMoveDollars: num(em.dollars), expectedMovePct: num(em.pct), expectedMoveRemaining: num(em.remaining_dollars),
      hedgeBuckets: (p.hedge_buckets || []).map(function (b) { return { shockBp: num(b.shock_bp), dS: num(b.dS), notionalM: num(b.notional_m), direction: b.direction || null }; }),
      dealerGammaPerPtM: num(p.dealer_gamma_notional_m_per_pt), speedMPerPt2: num(g.speed_m_per_pt2), speedWideMPerPt2: num(g.speed_wide_m_per_pt2),
      reversalConditions: (p.reversal_watch && p.reversal_watch.conditions) || [], reversalStretched: p.reversal_watch ? !!p.reversal_watch.stretched : null,
      pcVolume: num(fl.pc_volume), pcOi: num(fl.pc_oi), callVolume: num(fl.call_volume), putVolume: num(fl.put_volume),
      atmCallIv: num(iv.atm_call_iv), atmPutIv: num(iv.atm_put_iv), riskReversal25d: num(iv.risk_reversal_25d), totalVannaK: num(vc.total_vanna_k), totalCharmK: num(vc.total_charm_k),
      byStrike: by, strikeCoverage: { total: by.length, gexKnown: known, gexMissing: by.length - known },
      topStrikes: (g.top_strikes || []).map(function (s) { return { strike: num(s.strike), netGexM: num(s.net_gex_m), callGexM: num(s.call_gex_m), putGexM: num(s.put_gex_m) }; }),
      elevatedActivity: (fl.elevated_volume_activity || []).map(function (a) { return { strike: num(a.strike), side: a.side || '', volume: num(a.volume), oi: num(a.oi), volOi: num(a.vol_oi), notionalK: num(a.notional_k) }; }),
      rtdStrikes: num(f.n_strikes_rtd_live), nasdaqStrikes: num(f.n_strikes_nasdaq_delayed), nasdaqAsOf: src.nasdaq ? src.nasdaq.as_of || null : null, nasdaqStale: src.nasdaq ? !!src.nasdaq.stale : null,
      quoteSource: src.quote || null, chainSource: chainSource(src)
    };
  }
  // The single declared chain-provider entry: any key other than the nasdaq wings and the quote block (rev3 contract).
  function chainSource(src) {
    var keys = Object.keys(src || {}).filter(function (k) { return k !== 'nasdaq' && k !== 'quote' && src[k] && typeof src[k] === 'object'; });
    if (keys.length !== 1) return null;
    var k = keys[0], e = src[k];
    return { name: k, delay: e.delay || null, asOf: e.as_of || null, n: num(e.n_strikes) };
  }
  // Quote clock wording from provenance: a collector receipt is not an event time; a provider as-of has unverified latency.
  function quoteClockLabel(q) {
    if (!q || !q.source) return 'no quote clock';
    if (q.clock === 'collector-receipt') return 'collector receipt';
    if (q.clock === 'provider-as-of') return 'provider as-of (latency unverified)';
    return 'clock kind not stated';
  }
  function ladderModel(live) {
    var spot = live.spot, em = live.expectedMoveRemaining !== null ? live.expectedMoveRemaining : live.expectedMoveDollars;
    if (spot === null) return null;
    var pts = [spot]; [live.putWall, live.callWall, live.gammaFlip, live.maxPain].forEach(function (v) { if (v !== null) pts.push(v); });
    if (em !== null) { pts.push(spot - em); pts.push(spot + em); }
    var rawMin = Math.min.apply(null, pts), rawMax = Math.max.apply(null, pts), pad = Math.max(1, (rawMax - rawMin) * 0.12);
    var min = Math.floor((rawMin - pad) * 2) / 2, max = Math.ceil((rawMax + pad) * 2) / 2;
    var pos = function (v) { return ((v - min) / (max - min)) * 100; };
    var markers = [
      { key: 'call', label: 'CALL WALL', value: live.callWall, lane: 'above', digits: 0 },
      { key: 'spot', label: 'SPOT', value: spot, lane: 'above', digits: 2, bold: true },
      { key: 'flip', label: 'FLIP', value: live.gammaFlip, lane: 'below', digits: 2 },
      { key: 'pain', label: 'MAX PAIN', value: live.maxPain, lane: 'below', digits: 0 },
      { key: 'put', label: 'PUT WALL', value: live.putWall, lane: 'below', digits: 0 }
    ].filter(function (m) { return m.value !== null; }).map(function (m) { m.x = pos(m.value); return m; });
    function layout(lane) {
      var items = markers.filter(function (m) { return m.lane === lane; }).sort(function (a, b) { return a.x - b.x; }), rows = [];
      items.forEach(function (it) { var placed = false; for (var i = 0; i < rows.length; i++) { var last = rows[i][rows[i].length - 1]; if (!last || it.x - last.x >= 27) { rows[i].push(it); placed = true; break; } } if (!placed) rows.push([it]); });
      return rows;
    }
    return { min: min, max: max, em: em, markers: markers, above: layout('above'), below: layout('below'), band: em !== null ? { left: pos(spot - em), width: pos(spot + em) - pos(spot - em) } : null };
  }
  function gexBars(live, half) { if (half === undefined) half = 14; var s = live.spot; return live.byStrike.filter(function (b) { return b.netGexM !== null && (s === null || Math.abs(b.strike - s) <= half); }); }
  function trailUpdate(trail, live, nowMs) {
    // one point per minute by updated_at; keep ~5 calendar days (covers three trading days across a weekend)
    var t = parseAwareMs(live.updatedAt); if (t === null) return trail;
    var keep = (trail || []).filter(function (p) { return nowMs - p.t <= 5 * 86400000; });
    var last = keep[keep.length - 1];
    if (last && t - last.t < 60000) return keep;
    if (last && t <= last.t) return keep;
    keep.push({ t: t, spot: live.spot, callWall: live.callWall, putWall: live.putWall, flip: live.gammaFlip, maxPain: live.maxPain });
    return keep.slice(-4320);
  }
  var api = { computeStatus: computeStatus, feedAgeMs: feedAgeMs, parseAwareMs: parseAwareMs, normalize: normalize, chainSource: chainSource, quoteClockLabel: quoteClockLabel, ladderModel: ladderModel, gexBars: gexBars, trailUpdate: trailUpdate, clusterState: clusterState, fmt: fmt, fmtMoneyM: fmtMoneyM, STALE_AFTER_MS: STALE_AFTER_MS };
  if (typeof module === 'object' && module.exports) { module.exports = api; return; }

  // ---- DOM ----
  var doc = root.document, $ = function (id) { return doc.getElementById(id); };
  var SVG = 'http://www.w3.org/2000/svg';
  function el(tag, cls, text) { var e = doc.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function svgEl(tag, attrs) { var e = doc.createElementNS(SVG, tag); Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, String(attrs[k])); }); return e; }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function store(key, val) { try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) {} }
  function load(key) { try { var v = localStorage.getItem(key); return v ? JSON.parse(v) : null; } catch (e) { return null; } }

  var state = { paused: false, feed: null, signals: null, signalsOk: false, lastGood: load('dash.lastGood'), trail: load('dash.trail') || [], error: null, fetching: false, hadResponse: false };

  function setStatus(status, display, nowMs) {
    var labels = { live: 'LIVE', stale: 'STALE', down: 'FEED DOWN', closed: 'MARKET CLOSED', paused: 'PAUSED' };
    var lbl = $('statusLabel'), dot = $('statusDot');
    lbl.textContent = labels[status]; lbl.className = 's-' + status; dot.className = 'dot s-' + status + (status === 'live' ? ' pulse' : '');
    $('statusMeta').textContent = 'SPY · 0DTE' + (display && display.expiry ? ' · exp ' + display.expiry : '') + (display ? ' · updated ' + fmtTime(display.updatedAt) + ' PT (' + ageLabel(display.updatedAt, nowMs) + ')' : '');
  }
  function renderLadder(live) {
    var m = ladderModel(live), above = $('laneAbove'), below = $('laneBelow'), ticks = $('ticks');
    clear(above); clear(below); clear(ticks);
    if (!m) { $('ladder').hidden = true; return; }
    $('ladder').hidden = false;
    var ROW = 17;
    function lane(host, rows, reverse) {
      host.style.height = Math.max(1, rows.length) * ROW + 'px';
      rows.forEach(function (row, ri) { row.forEach(function (it) { var d = el('div', 'lbl ' + it.key, it.label + ' ' + fmt(it.value, it.digits)); d.style.left = Math.min(90, Math.max(10, it.x)) + '%'; d.style.top = (reverse ? (rows.length - 1 - ri) : ri) * ROW + 'px'; host.appendChild(d); }); });
    }
    lane(above, m.above, true); lane(below, m.below, false);
    m.markers.forEach(function (it) { var t = el('div', 'tick ' + it.key); t.style.left = it.x + '%'; ticks.appendChild(t); });
    var band = $('band'); if (m.band) { band.hidden = false; band.style.left = m.band.left + '%'; band.style.width = m.band.width + '%'; } else { band.hidden = true; }
    $('ladderMin').textContent = fmt(m.min, 1); $('ladderMax').textContent = fmt(m.max, 1); $('ladderBand').textContent = m.em !== null ? 'shaded band = expected move ±' + fmt(m.em) : '';
  }
  function renderGex(live) {
    var svg = $('gexChart'); clear(svg); var data = gexBars(live);
    if (!data.length) { svg.appendChild(svgEl('text', { x: 320, y: 110, 'text-anchor': 'middle', fill: 'var(--dim)', 'font-size': 13 })).textContent = 'No strike GEX data in this snapshot.'; return; }
    var W = 640, H = 230, L = 48, R = 8, T = 10, B = 26, iw = W - L - R, ih = H - T - B;
    var vals = data.map(function (d) { return d.netGexM; }), lo = Math.min(0, Math.min.apply(null, vals)), hi = Math.max(0, Math.max.apply(null, vals)); if (hi === lo) hi = lo + 1;
    var y = function (v) { return T + (hi - v) / (hi - lo) * ih; }, bw = iw / data.length;
    [lo, (lo + hi) / 2, hi, 0].forEach(function (v) { var yy = y(v); svg.appendChild(svgEl('line', { x1: L, x2: W - R, y1: yy, y2: yy, stroke: v === 0 ? 'var(--dim)' : 'var(--border)', 'stroke-dasharray': v === 0 ? '' : '2 4' })); var t = svgEl('text', { x: L - 6, y: yy + 4, 'text-anchor': 'end', fill: 'var(--dim)', 'font-size': 10, 'font-family': 'var(--mono)' }); t.textContent = '$' + fmt(v, 0); svg.appendChild(t); });
    data.forEach(function (d, i) { var x = L + i * bw, h = Math.abs(y(d.netGexM) - y(0)); var r = svgEl('rect', { x: x + bw * 0.12, y: Math.min(y(d.netGexM), y(0)), width: Math.max(1, bw * 0.76), height: Math.max(0.5, h), fill: d.netGexM >= 0 ? 'var(--gamma-pos)' : 'var(--gamma-neg)', rx: 1.5 }); var tt = svgEl('title'); tt.textContent = 'Strike ' + fmt(d.strike, 0) + ': $' + fmt(d.netGexM, 1) + 'M'; r.appendChild(tt); svg.appendChild(r); });
    var step = Math.max(1, Math.ceil(data.length / 8));
    data.forEach(function (d, i) { if (i % step === 0 || i === data.length - 1) { var t = svgEl('text', { x: L + i * bw + bw / 2, y: H - 8, 'text-anchor': 'middle', fill: 'var(--dim)', 'font-size': 10, 'font-family': 'var(--mono)' }); t.textContent = fmt(d.strike, 0); svg.appendChild(t); } });
    var cov = live.strikeCoverage; $('gexNote').textContent = 'Windowed to spot ±14. Green = positive gamma strike, red = negative. Walls and flip are computed over the full chain.' + (cov && cov.gexMissing > 0 ? ' Strike GEX coverage: ' + cov.gexKnown + ' of ' + cov.total + ' strikes reported — ' + cov.gexMissing + ' unavailable, excluded (not zeroed).' : '');
  }
  function renderTrail() {
    var svg = $('trailChart'); clear(svg); var tr = state.trail;
    if (tr.length < 2) { $('trailNote').textContent = 'The trail builds as snapshots accumulate while this page is open — one point per minute, kept for the last three trading days.'; return; }
    $('trailNote').textContent = tr.length + ' points · spot (bright), call wall, put wall, flip (dashed), max pain (dotted)';
    var W = 640, H = 210, L = 50, R = 8, T = 10, B = 26, iw = W - L - R, ih = H - T - B;
    var all = []; tr.forEach(function (p) { ['spot', 'callWall', 'putWall', 'flip', 'maxPain'].forEach(function (k) { if (num(p[k]) !== null) all.push(p[k]); }); });
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all); if (hi === lo) { hi += 1; lo -= 1; } var pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
    var x = function (i) { return L + i / (tr.length - 1) * iw; }, y = function (v) { return T + (hi - v) / (hi - lo) * ih; };
    [lo, (lo + hi) / 2, hi].forEach(function (v) { svg.appendChild(svgEl('line', { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: 'var(--border)', 'stroke-dasharray': '2 4' })); var t = svgEl('text', { x: L - 6, y: y(v) + 4, 'text-anchor': 'end', fill: 'var(--dim)', 'font-size': 10, 'font-family': 'var(--mono)' }); t.textContent = fmt(v, 0); svg.appendChild(t); });
    function line(key, color, dash, width, step) { var d = '', pen = false; tr.forEach(function (p, i) { var v = num(p[key]); if (v === null) { pen = false; return; } var px = x(i), py = y(v); if (!pen) { d += 'M' + px + ' ' + py; pen = true; } else if (step) { d += ' H' + px + ' V' + py; } else { d += ' L' + px + ' ' + py; } }); svg.appendChild(svgEl('path', { d: d, fill: 'none', stroke: color, 'stroke-width': width, 'stroke-dasharray': dash || '' })); }
    line('callWall', 'var(--call)', '', 1.5, true); line('putWall', 'var(--put)', '', 1.5, true); line('flip', 'var(--flip)', '4 3', 1.5, true); line('maxPain', 'var(--dim)', '2 3', 1.5, true); line('spot', 'var(--amber-bright)', '', 2.25, false);
    var n = Math.min(6, tr.length); for (var k = 0; k < n; k++) { var i = Math.round(k * (tr.length - 1) / (n - 1 || 1)); var t = svgEl('text', { x: x(i), y: H - 8, 'text-anchor': 'middle', fill: 'var(--dim)', 'font-size': 10, 'font-family': 'var(--mono)' }); t.textContent = fmtTimeShort(new Date(tr[i].t).toISOString()); svg.appendChild(t); }
  }
  function stat(label, value, sub) { var d = el('div', 'stat'); d.appendChild(el('div', 'label', label)); d.appendChild(el('div', 'v', value)); if (sub) d.appendChild(el('div', 'sub', sub)); return d; }
  function dirMark(dir) { var s = el('span', dir === 'bull' ? 'bull' : dir === 'bear' ? 'bear' : 'd', dir === 'bull' ? '▲' : dir === 'bear' ? '▼' : '•'); return s; }
  function renderSignals(sig, live) {
    $('speed').textContent = 'Speed: ' + fmt(live.speedMPerPt2, 1) + ' / wide ' + fmt(live.speedWideMPerPt2, 1) + ' $M/pt²';
    var gun = $('gun'), pr = $('pressure'), st = $('stacks'), ex = $('extremes'), ch = $('charm'); clear(gun); clear(st); clear(ex); clear(pr);
    if (!sig || !state.signalsOk) { gun.className = 'mono small'; gun.textContent = "Signals unavailable — the interpreter's /feed/signals did not answer. The rest of this page is unaffected."; pr.hidden = true; ch.hidden = true; return; }
    var sp = sig.session_pressure;
    if (sp && sp.verdict) { pr.hidden = false; pr.appendChild(el('b', '', 'Session pressure: ' + sp.verdict)); pr.appendChild(el('div', '', sp.line || '')); if (sp.what_changes_it) pr.appendChild(el('div', 'd', sp.what_changes_it)); } else { pr.hidden = true; }
    var lg = sig.loaded_gun || {};
    if (lg.active) { gun.className = 'gun mono'; gun.appendChild(el('b', '', '🔫 LOADED GUN')); gun.appendChild(el('div', 'small', 'since ' + (lg.since_et || '—') + ' ET · spot ' + fmt(lg.spot) + ' · pin ' + fmt(lg.pin, 0) + ' · net GEX ' + fmtMoneyM(lg.net_gex_m) + ' · budget left ' + (num(lg.budget_left) !== null ? fmt(lg.budget_left * 100, 0) + '%' : '—') + (num(lg.flip_dist) !== null ? ' · flip dist ' + fmt(lg.flip_dist) : ''))); }
    else { gun.className = 'mono small'; gun.textContent = 'Loaded gun: off'; }
    var ct = sig.last_charm_trigger; if (ct) { ch.hidden = false; ch.textContent = '🎯 Last charm trigger ' + (ct.ts_et || '—') + ' ET — SPY ' + fmt(ct.spot) + ', charm velocity ' + fmtInt(ct.charm_vel30); } else { ch.hidden = true; }
    var stacks = sig.stacks || [];
    if (!stacks.length) st.appendChild(el('p', 'empty', 'No stacks yet today.'));
    stacks.forEach(function (s) { var d = (s.detail || {}); var r = el('div', 'row'); r.appendChild(el('span', 'd', fmtEtTime(s.ts_et) + ' ET')); r.appendChild(el('b', '', s.symbol || '')); r.appendChild(dirMark(s.direction)); r.appendChild(el('span', '', fmt(s.spot))); if (d.path) r.appendChild(el('span', 'd', 'path ' + d.path)); if (d.members && d.members.length) { var m = el('div', 'd', d.members.join(' + ')); m.style.width = '100%'; r.appendChild(m); } st.appendChild(r); });
    var exs = sig.extremes || [];
    if (!exs.length) ex.appendChild(el('p', 'empty', 'No extremes flagged yet today.'));
    exs.forEach(function (e) { var d = e.detail || {};
      if (e.type === 'vol_ignition') { var cs = clusterState(d.cluster, d.prints_60m); var c = el('div', 'print'); var r = el('div', 'row'); r.appendChild(el('span', '', '🖨️')); r.appendChild(el('span', 'd', fmtEtTime(e.ts_et) + ' ET')); r.appendChild(el('b', '', e.symbol || '')); r.appendChild(dirMark(e.direction)); r.appendChild(el('span', '', fmt(e.spot))); r.appendChild(el('b', '', fmtInt(d.vol) + ' shares')); if (num(d.mult) !== null) r.appendChild(el('span', '', fmt(d.mult, 1) + '× median')); if (d.mega === true) r.appendChild(el('span', 'badge', 'MEGA')); if (d.at_lows === true) r.appendChild(el('span', '', 'at lows')); if (d.at_highs === true) r.appendChild(el('span', '', 'at highs')); c.appendChild(r); c.appendChild(el('div', cs.kind === 'clustering' ? 'warn' : 'd', cs.text)); ex.appendChild(c); }
      else { var r2 = el('div', 'row'); r2.appendChild(el('span', 'd', fmtEtTime(e.ts_et) + ' ET')); r2.appendChild(el('b', '', e.symbol || '')); r2.appendChild(el('span', '', e.type || '')); r2.appendChild(dirMark(e.direction)); r2.appendChild(el('span', '', fmt(e.spot))); ex.appendChild(r2); } });
  }
  function render() {
    var nowMs = Date.now(), live = state.feed ? normalize(state.feed) : null, display = live || state.lastGood, showingStale = live === null && display !== null;
    var ageMs = display ? feedAgeMs(display.updatedAt, nowMs) : null;
    var status = computeStatus({ paused: state.paused, hasData: state.hadResponse, isError: !!state.error, showingStale: showingStale, dataOk: !!(state.feed && state.feed.status === 'ok'), marketOpen: display ? display.marketOpen : null, ageMs: ageMs });
    setStatus(status, display, nowMs);
    var banner = $('banner'); banner.hidden = true; banner.className = 'banner mono';
    if (showingStale) { banner.hidden = false; banner.className += ' alert'; banner.textContent = 'Interpreter feed unreachable' + (state.error ? ' (' + state.error + ')' : state.feed && state.feed.status !== 'ok' ? ' (' + state.feed.status + (state.feed.error ? ': ' + state.feed.error : '') + ')' : '') + ' — showing the last snapshot this page stored, from ' + fmtTime(display.updatedAt) + ' PT. Nothing below is live.'; }
    else if (status === 'closed') { banner.hidden = false; banner.textContent = 'Market closed — showing the latest interpreter snapshot. Levels update again at the next session.'; }
    var panels = ['hero', 'signalsPanel', 'gexPanel', 'pinPanel', 'trailPanel', 'flowPanel', 'topPanel', 'actPanel'];
    if (!display) { panels.forEach(function (id) { $(id).hidden = true; }); banner.hidden = false; banner.textContent = state.hadResponse ? 'No snapshot yet — the interpreter did not answer' + (state.error ? ' (' + state.error + ')' : state.feed && state.feed.status ? ' (' + state.feed.status + (state.feed.error ? ': ' + state.feed.error : '') + ')' : '') + ' and this page has no stored snapshot to fall back on.' : 'Connecting to the interpreter feed…'; return; }
    panels.forEach(function (id) { $(id).hidden = false; });
    $('spot').textContent = fmt(display.spot);
    var reg = $('regime'); reg.textContent = display.regime || 'regime —'; reg.className = 'regime mono' + (display.netGexM !== null && display.netGexM >= 0 ? ' pos' : '');
    $('heroMeta').textContent = 'Net GEX ' + fmtMoneyM(display.netGexM) + ' per 1% · flip ' + fmt(display.gammaFlip) + ' · quote ' + quoteClockLabel(display.quoteSource) + ' ' + fmtTime(display.quoteAsOf) + ' PT' + (display.quoteSource && display.quoteSource.source ? ' (' + display.quoteSource.source + ', ' + (display.quoteSource.delay || 'delay not stated') + ')' : '');
    renderLadder(display); renderSignals(state.signals, display); renderGex(display);
    $('pin').textContent = display.pinScore !== null ? fmt(display.pinScore, 0) : '—'; $('pinMeta').textContent = 'pin score / 100' + (display.pinMagnet !== null ? ' · magnet ' + fmt(display.pinMagnet, 0) : '');
    $('pinFill').style.width = Math.max(0, Math.min(100, display.pinScore || 0)) + '%';
    var pc = $('pinComps'); clear(pc); if (display.pinComponents) { [['concentration', 'concentration'], ['proximity', 'proximity'], ['session elapsed', 'timeElapsed']].forEach(function (p) { var s = el('span', '', p[0] + ' '); var v = display.pinComponents[p[1]]; s.appendChild(el('b', '', v !== null ? fmt(v * 100, 0) + '%' : '—')); pc.appendChild(s); }); }
    var hb = $('hedge'); clear(hb); if (!display.hedgeBuckets.length) hb.appendChild(el('p', 'empty', 'Unavailable in this snapshot.'));
    var maxAbs = Math.max.apply(null, display.hedgeBuckets.map(function (b) { return Math.abs(b.notionalM || 0); }).concat([1]));
    display.hedgeBuckets.forEach(function (b) { var row = el('div', 'hb'); row.appendChild(el('span', 'k', '±' + fmt(b.shockBp, 0) + 'bp')); var bar = el('div', 'bar2'); var sell = b.direction === 'sell' || (b.notionalM || 0) < 0; var fill = el('div', 'fill ' + (sell ? 'sell' : 'buy')); fill.style.width = (Math.abs(b.notionalM || 0) / maxAbs * 100) + '%'; bar.appendChild(fill); row.appendChild(bar); var v = el('span', 'v', fmtMoneyM(b.notionalM) + ' '); v.appendChild(el('span', 'd', b.direction || '')); row.appendChild(v); hb.appendChild(row); });
    var rv = $('reversal'); clear(rv); rv.hidden = !display.reversalConditions.length; display.reversalConditions.forEach(function (c) { rv.appendChild(el('p', '', '⚠ ' + c)); });
    state.trail = trailUpdate(state.trail, display, nowMs); store('dash.trail', state.trail); renderTrail();
    var fs = $('flowStats'); clear(fs);
    fs.appendChild(stat('Expected move', display.expectedMoveRemaining !== null ? '±' + fmt(display.expectedMoveRemaining) : '—', display.expectedMovePct !== null ? fmt(display.expectedMovePct, 3) + '% to expiry' : ''));
    fs.appendChild(stat('P/C volume', fmt(display.pcVolume), 'calls ' + fmtInt(display.callVolume) + ' · puts ' + fmtInt(display.putVolume)));
    fs.appendChild(stat('P/C open interest', fmt(display.pcOi)));
    fs.appendChild(stat('ATM IV', (display.atmCallIv !== null || display.atmPutIv !== null) ? (display.atmCallIv !== null ? fmt(display.atmCallIv * 100, 1) + '%' : '—') + ' / ' + (display.atmPutIv !== null ? fmt(display.atmPutIv * 100, 1) + '%' : '—') : '—', 'call / put'));
    fs.appendChild(stat('25Δ risk reversal', display.riskReversal25d !== null ? fmt(display.riskReversal25d * 100, 2) + ' vol pts' : 'unavailable', display.riskReversal25d !== null ? 'put25 − call25' : 'feed reports null — not estimated'));
    fs.appendChild(stat('Dealer γ / pt', fmtMoneyM(display.dealerGammaPerPtM), 'per 1pt spot move'));
    fs.appendChild(stat('Vanna (total)', display.totalVannaK !== null ? fmtInt(display.totalVannaK) + 'k' : '—'));
    fs.appendChild(stat('Charm (total)', display.totalCharmK !== null ? fmtInt(display.totalCharmK) + 'k' : '—'));
    var tb = $('topRows'); clear(tb); display.topStrikes.forEach(function (s) { var tr = el('tr'); var td = el('td'); td.appendChild(el('b', '', fmt(s.strike, 0))); tr.appendChild(td); var n = el('td', 'r' + (s.netGexM === null ? '' : s.netGexM >= 0 ? ' pos' : ' neg'), fmt(s.netGexM, 0)); tr.appendChild(n); tr.appendChild(el('td', 'r', fmt(s.callGexM, 0))); tr.appendChild(el('td', 'r', fmt(s.putGexM, 0))); tb.appendChild(tr); });
    var ac = $('activity'); clear(ac); if (!display.elevatedActivity.length) ac.appendChild(el('p', 'empty', 'None flagged in this snapshot.'));
    display.elevatedActivity.slice(0, 6).forEach(function (a) { var r = el('div', 'act'); var l = el('span'); l.appendChild(el('b', '', fmt(a.strike, 0) + ' ')); l.appendChild(el('span', a.side === 'put' ? 'put' : 'call', a.side)); r.appendChild(l); r.appendChild(el('span', 'd', 'vol/OI ' + fmt(a.volOi, 1) + ' · ' + (a.notionalK !== null ? '$' + fmtInt(a.notionalK) + 'k' : '—'))); ac.appendChild(r); });
    var cs = display.chainSource;
    $('foot').textContent = 'Source: interpreter on this host (/feed/all + /feed/signals, loopback :8788), snapshot every ~30 s. Quote: ' + (display.quoteSource && display.quoteSource.source ? display.quoteSource.source + ' · ' + (display.quoteSource.delay || 'delay not stated') + ' · ' + quoteClockLabel(display.quoteSource) + ' ' + fmtTime(display.quoteSource.as_of) + ' PT' : 'none') + '. Chain: ' + (cs ? cs.name + ' · ' + (cs.delay || 'delay not stated') + ' · ' + fmt(cs.n, 0) + ' strikes · provider as-of ' + (cs.asOf ? fmtTime(cs.asOf) + ' PT' : 'unknown') : 'no declared chain provider') + ' · ' + fmt(display.rtdStrikes, 0) + ' strikes real-time. Nasdaq wings: ' + fmt(display.nasdaqStrikes, 0) + ' strikes, ~15 min delayed' + (display.nasdaqStale ? ', STALE cache' : '') + (display.nasdaqAsOf ? ', as of ' + fmtTime(display.nasdaqAsOf) + ' PT' : '') + '. This page polls every 15 s while open and stores one snapshot per minute for the trail. GEX convention: dealers long calls / short puts — an assumption, not observed positioning. Nothing here predicts direction.';
    if (live) { state.lastGood = live; store('dash.lastGood', live); }
  }
  function fetchJson(url) { return fetch(url, { cache: 'no-store', credentials: 'same-origin' }).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }); }
  function refresh() {
    if (state.fetching) return; state.fetching = true; $('refreshBtn').textContent = 'Refreshing…';
    Promise.all([
      fetchJson('/feed/all').then(function (j) { state.feed = j; state.error = null; }, function (e) { state.feed = null; state.error = String(e.message || e); }),
      fetchJson('/feed/signals').then(function (j) { state.signals = j; state.signalsOk = j && j.status === 'ok'; }, function () { state.signals = null; state.signalsOk = false; })
    ]).then(function () { state.hadResponse = true; state.fetching = false; $('refreshBtn').textContent = 'Refresh'; render(); });
  }
  $('pauseBtn').addEventListener('click', function () { state.paused = !state.paused; $('pauseBtn').textContent = state.paused ? 'Resume' : 'Pause'; render(); });
  $('refreshBtn').addEventListener('click', refresh);
  doc.addEventListener('visibilitychange', function () { if (!doc.hidden && !state.paused) refresh(); });
  render(); refresh();
  setInterval(function () { if (!state.paused) refresh(); }, POLL_MS);
  setInterval(function () { if (state.hadResponse) render(); }, 10000);
})(typeof globalThis === 'object' ? globalThis : this);
