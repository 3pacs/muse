// Offline provenance rendering on exact bb1763ff dashboard export. node helper EXPORT_ROOT OUT_DIR
// Fake DOM records text only; fetch is an in-memory stub. No browser/CSP/layout/runtime claim.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
const req = createRequire(import.meta.url);
const [root, out] = process.argv.slice(2);
const jsPath = path.resolve(root, 'stopgap-20261022-dashboard/page/dashboard.js');
const fixturePath = path.resolve(root, 'stopgap-20261022-dashboard/tests/fixture-feed-all.json');
const sha = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
if (sha(jsPath) !== 'b75b19d8af9a1c30e3736011ff9c4e6b64c2627956ff75115adaf23292e60a72') throw Error('source changed');
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
rec('renderer-unknown-clock-is-not-epoch', unknownRendered.hero.includes('quote as of —') && !unknownRendered.hero.includes('1969'), unknownRendered.hero);
const alternate=structuredClone(cap);alternate.sources.vendor_delayed=alternate.sources.cboe_delayed;delete alternate.sources.cboe_delayed;
const other=D.normalize(alternate);
rec('normalizer-retains-declared-alternate-chain-provider', other.chainSource?.name==='vendor_delayed', other.chainSource);
const report={local_export_commit:'bb1763ff98f44ab6ed2de41fb05cbe9f194d7302', dashboard_source_commit:'47c504052d15234e454fe11a81e9049eaee7040b',
  dashboard_js_sha256:sha(jsPath),fixture_sha256:sha(fixturePath),helper_sha256:sha(new URL(import.meta.url)),
  mode:'Exact-source pure exports and in-memory fake-DOM text rendering. Native fetch/provider/database/server/browser UNRUN.',
  passed:checks.filter(c=>c.passed).length,total:checks.length,checks};
fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'independent-render.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({passed:report.passed,total:report.total}));
for(const c of checks)if(!c.passed)console.log('FAIL',c.name);
process.exitCode=report.passed===report.total?0:1;
