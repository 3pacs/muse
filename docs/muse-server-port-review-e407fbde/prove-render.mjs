// Offline provenance rendering on exact e407fbde uploaded dashboard. node helper PACKET_DIR CAPTURE OUT_DIR
// Fake DOM records text only; fetch is an in-memory stub. No browser/CSP/layout/runtime claim.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
const req = createRequire(import.meta.url);
const [root, capture, out] = process.argv.slice(2);
const jsPath = path.resolve(root, 'dashboard.js');
const fixturePath = path.resolve(capture);
const sha = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
if (sha(jsPath) !== '4f98536fe82b6ffa350da06741f29124e9fb5259bf277c97741767a69423f65f') throw Error('source changed');
const code = fs.readFileSync(jsPath, 'utf8'), D = req(jsPath);
const cap = JSON.parse(fs.readFileSync(fixturePath)), checks = [];
function rec(name, passed, actual) { checks.push({name, passed:!!passed, actual}); }
class Element {
  constructor() { this.children=[];this.style={};this.textContent='';this.hidden=false; }
  get firstChild() { return this.children[0]; }
  appendChild(c) { this.children.push(c); return c; }
  removeChild(c) { this.children.splice(this.children.indexOf(c),1); }
  setAttribute() {} addEventListener() {}
}
async function render(feed) {
  const nodes = {}, doc = {getElementById:id => nodes[id] ||= new Element(), createElement:()=>new Element(), createElementNS:()=>new Element(), addEventListener() {}};
  let fetches = 0;
  const sandbox = {document:doc, console, Intl, Date, localStorage:{getItem:()=>null,setItem(){}}, setInterval() {},
    fetch:async url => {fetches++; if(!['/feed/all','/feed/signals'].includes(url)) throw Error('unexpected fetch');return {ok:true,json:async()=>url==='/feed/all'?feed:{status:'ok',stacks:[],extremes:[]}};}};
  vm.runInNewContext(code, sandbox, {timeout:5000});
  for(let i=0;i<8;i++) await new Promise(resolve=>setImmediate(resolve));
  if(fetches!==2) throw Error('unexpected fetch count');
  return {hero:nodes.heroMeta.textContent, footer:nodes.foot.textContent};
}
const normalized=D.normalize(cap), chain=cap.sources.cboe_delayed;
rec('normalizer-retains-cboe-provenance', normalized.chainSource?.name==='cboe_delayed' && normalized.chainSource?.asOf===chain.as_of && normalized.chainSource?.delay===chain.delay && normalized.chainSource?.n===chain.n_strikes, normalized.chainSource);
rec('normalizer-retains-quote-clock-kind', normalized.quoteSource?.clock==='collector-receipt', normalized.quoteSource);
const actual = await render(cap);
rec('renderer-shows-delayed-chain-and-zero-live-option-strikes', actual.footer.includes('cboe_delayed') && actual.footer.includes('~15min') && actual.footer.includes('0 strikes real-time'), actual.footer);
rec('renderer-labels-collector-receipt-clock-kind', /collector|receipt/i.test(actual.hero+' '+actual.footer), {hero:actual.hero,reason:'RTD callback receipt must remain distinct from market/provider time'});
const pub=structuredClone(cap);pub.sources.quote={source:'public_price',delay:'latency-unverified',as_of:cap.quote_as_of,clock:'provider-as-of'};
const pubRendered=await render(pub);
rec('renderer-labels-public-fallback-latency', pubRendered.hero.includes('public_price, latency-unverified'), pubRendered.hero);
const unknown=structuredClone(cap);unknown.sources.quote.as_of=null;unknown.quote_as_of=null;
const unknownRendered=await render(unknown);
rec('renderer-unknown-clock-is-not-epoch', unknownRendered.hero.includes('collector receipt —') && !unknownRendered.hero.includes('1969'), unknownRendered.hero);
const alternate=structuredClone(cap);alternate.sources.vendor_delayed=alternate.sources.cboe_delayed;delete alternate.sources.cboe_delayed;
const other=D.normalize(alternate);
rec('normalizer-retains-declared-alternate-chain-provider', other.chainSource?.name==='vendor_delayed', other.chainSource);
rec('renderer-labels-public-provider-clock', pubRendered.hero.includes('provider as-of (latency unverified)') && pubRendered.footer.includes('provider as-of (latency unverified)'), pubRendered.hero);
const legacy=structuredClone(cap);delete legacy.sources.quote.clock;
const legacyRendered=await render(legacy);
rec('renderer-legacy-clock-kind-remains-unknown', legacyRendered.hero.includes('clock kind not stated') && !legacyRendered.hero.includes('collector receipt'), legacyRendered.hero);
const both=structuredClone(cap);both.sources.rtd={as_of:null,delay:'realtime',n_strikes:3};
rec('normalizer-two-chain-providers-fail-closed', D.normalize(both).chainSource===null, D.normalize(both).chainSource);
const noChain=structuredClone(cap);delete noChain.sources.cboe_delayed;
rec('normalizer-no-chain-provider-fail-closed', D.normalize(noChain).chainSource===null, D.normalize(noChain).chainSource);
const otherRendered=await render(alternate);
rec('renderer-shows-alternate-provider-without-rtd-reassignment', otherRendered.footer.includes('Chain: vendor_delayed') && otherRendered.footer.includes('~15min'), otherRendered.footer);
const report={packet_commit:'e407fbde8cbb51147e5104863e9dd80a44ead747', local_source_commit:'5c861f477aa4a7a0b1cb74d3af73885bb6a348ac',
  dashboard_js_sha256:sha(jsPath),fixture_sha256:sha(fixturePath),helper_sha256:sha(new URL(import.meta.url)),
  mode:'Exact-source pure exports and in-memory fake-DOM text rendering. Native fetch/provider/database/server/browser UNRUN.',
  passed:checks.filter(c=>c.passed).length,total:checks.length,checks};
fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'independent-render.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({passed:report.passed,total:report.total}));
for(const c of checks)if(!c.passed)console.log('FAIL',c.name);
process.exitCode=report.passed===report.total?0:1;
