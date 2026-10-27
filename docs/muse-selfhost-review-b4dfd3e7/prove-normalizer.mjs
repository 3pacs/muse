import fs from 'node:fs';import vm from 'node:vm';import path from 'node:path';import crypto from 'node:crypto';
const [base,input,out]=process.argv.slice(2);const source=fs.readFileSync(path.join(base,'server/src/actions.ts'),'utf8'),app=fs.readFileSync(path.join(base,'client/src/App.tsx'),'utf8');const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
if(sha(source)!=='247b3ecaa8d8d4107868c7407271bf4c46bc9a9c22013fc2c388d420fccddd55')throw Error('Expected exact published C07 actions source');
function takeFunction(name){const m=new RegExp('^(?:async )?function '+name+'\\(','m').exec(source);if(!m)throw Error(name);const begin=m.index,open=name==='fetchFeed'?source.indexOf('> {',begin)+2:source.indexOf('{',begin);return takeBody(begin,open);}
function takeBody(begin,open){let depth=0,q=null,escape=false,line=false,comment=false;for(let i=open;i<source.length;i++){const c=source[i],n=source[i+1];if(line){if(c==='\n')line=false;continue;}if(comment){if(c==='*'&&n==='/'){comment=false;i++;}continue;}if(q){if(escape)escape=false;else if(c==='\\')escape=true;else if(c===q)q=null;continue;}if(c==='/'&&n==='/'){line=true;i++;continue;}if(c==='/'&&n==='*'){comment=true;i++;continue;}if(c==='"'||c==="'"||c==='\x60'){q=c;continue;}if(c==='{')depth++;if(c==='}'&&--depth===0)return source.slice(begin,i+1);}throw Error('unclosed source');}
function erase(s){return s
.replace(/: StaleSnapshotReason\b/g,'')
.replace(/: PersistenceOutcome\["reason"\]/g,'').replace(/: PersistenceOutcome;/g,';').replace(/ as \{ code\?: unknown \} \| null/g,'').replace(/ as \{ rowsAffected\?: number \} \| undefined/g,'')
.replace(/async function maybePersistSnapshot\([\s\S]*?\): Promise<PersistenceOutcome> \{/,'async function maybePersistSnapshot(ctx,payload,rawJson) {')
.replace(/async function loadTrailAndLatest\([\s\S]*?\}> \{/,'async function loadTrailAndLatest(ctx) {')
.replace(/ctx\.db<typeof schema>\(\)/g,'ctx.db()')
.replace(/ as Record<\s*string,\s*unknown\s*>/g,'')
.replace(/async function fetchFeed\(\): Promise<[\s\S]*?> \{/,'async function fetchFeed() {')
.replace(/: LivePayload\["hedgeBuckets"\]/g,'').replace(/: LivePayload \| null/g,'')
.replace(/function strikeCoverage\([\s\S]*?\n\): \{[^\n]*\} \{/,'function strikeCoverage(rows) {')
.replace(/: Record<string, unknown>/g,'').replace(/ as Record<string, unknown>/g,'')
.replace(/: z\.infer<typeof (?:strikeGex|activityRow)>\[\]/g,'')
.replace(/: [mc] is string/g,'')
.replace(/: unknown/g,'').replace(/: number \| null/g,'').replace(/: string \| null/g,'').replace(/: (?:boolean|number|string)\b/g,'');}

const pure=source.slice(source.indexOf('// === ADOPT-F1 PURE HELPERS'),source.indexOf('// === END ADOPT-F1 PURE HELPERS ==='));
const transformed=erase(pure+'\n'+['mapActivity','normalize'].map(takeFunction).join('\n'));
const raw=JSON.parse(fs.readFileSync(input,'utf8'));const NOW=Date.parse(raw.updated_at)+1000;class FixedDate extends Date{static now(){return NOW;}}
const sandbox={Date:FixedDate,Number,Array,Object,Math,JSON};vm.createContext(sandbox);vm.runInContext(transformed+'\nthis.reviewNormalize=normalize;',sandbox);const normalized=sandbox.reviewNormalize(raw);
const fields=['sources','chainProvider','chainAsOf','chainDelay','quoteSource','quoteClock'];const aggregatePreserved=fields.some(k=>Object.hasOwn(normalized,k));
const receipt={source_commit:'29817f052543f91bf1a978daa1f60439bd2df298',actions_sha256:sha(source),app_sha256:sha(app),input_sha256:sha(fs.readFileSync(input)),helper_sha256:sha(fs.readFileSync(new URL(import.meta.url))),mode:'Exact published pure normalization source with disclosed type erasure; generated offline port snapshot input. No fetch, DB, React render, RPC, provider or server operation.',normalized_exists:normalized!==null,raw_provenance:{sources:raw.sources,rtdStrikes:raw.n_strikes_rtd_live,nasdaqStrikes:raw.n_strikes_nasdaq_delayed},normalized_provenance:{rtdStrikes:normalized.rtdStrikes,nasdaqStrikes:normalized.nasdaqStrikes,quoteAsOf:normalized.quoteAsOf,nasdaqAsOf:normalized.nasdaqAsOf,perStrikeSources:[...new Set(normalized.byStrike.map(x=>x.src))]},aggregate_provider_quote_clock_mapping_preserved:aggregatePreserved,footer_source_has_cboe:app.includes('cboe'),footer_source_hardcodes_rtd_nasdaq:app.includes('strikes realtime) + Nasdaq public'),pass:aggregatePreserved&&app.includes('cboe'),qualification:'Per-strike src survives, but aggregate Cboe provider/as_of/delay and sources.quote clock/source do not. Published footer remains RTD+Nasdaq; actual hosted artifact version/runtime rendering unverified.',native_provider_calls:0};
fs.writeFileSync(out,JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt,null,2));process.exitCode=receipt.pass?0:1;
