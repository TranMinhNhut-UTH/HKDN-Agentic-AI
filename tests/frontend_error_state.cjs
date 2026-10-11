// Execute the actual frontend in a VM with a minimal DOM/fetch fixture.
// This is a unit test, not browser automation or visual QA.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor() { this.children = []; this._text = ''; this.hidden = false; this.disabled = false; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(e => e.textContent).join(''); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this._text = ''; this.children = children; }
  addEventListener() {}
}
async function scenario(run, reportFailure = false, runFailure = false) {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  let timer = null;
  const context = vm.createContext({
    document: {getElementById:get, createElement: () => new Element()}, URL, Date, console,
    clearInterval: () => { timer = null; }, setInterval: callback => { timer = callback; return 1; },
    fetch: async url => {
      if (url === '/api/config') return {ok:true,json:async()=>({mode:'live',max_api_calls:16,max_steps:8,max_plans:2})};
      if (url === '/api/runs') return {ok:true,json:async()=>[]};
      if (url.startsWith('/api/reports/')) {
        if (reportFailure) throw Error('Download unavailable');
        return {ok:true,json:async()=>({id:'report',mode:'live',topic:'AI',articles:[],analysis:{findings:[]},requested_count:1,api_calls:4,created_at:new Date().toISOString(),warning:'budget'})};
      }
      if (runFailure) throw Error('Network unavailable');
      return {ok:true,json:async()=>run};
    }
  });
  vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
  await vm.runInContext('watchRun("test-run")', context);
  await new Promise(resolve => setImmediate(resolve));
  return {get, timer};
}
(async () => {
  for (const run of [
    {status:'failed',steps:[],report_id:null,error:'ServerError HTTP=503 message=Unavailable'},
    {status:'failed',steps:[],report_id:null,error:null},
    {status:'incomplete',steps:[],report_id:null,error:'BudgetExceeded'},
  ]) {
    const {get,timer} = await scenario(run);
    assert(!get('articles').textContent.includes('Đang tải'));
    assert(get('report-title').textContent.includes('Chưa tạo'));
    assert.equal(get('downloads').hidden, true);
    assert.equal(get('run-button').disabled, false);
    assert.equal(timer, null);
  }
  const failed = await scenario({status:'failed',steps:[],report_id:null,error:'HTTP=503'});
  assert(failed.get('articles').textContent.includes('HTTP=503'));
  for (const [reportFailure,runFailure] of [[true,false],[false,true]]) {
    const {get} = await scenario({status:'completed',steps:[],report_id:'report'}, reportFailure, runFailure);
    assert(!get('articles').textContent.includes('Đang tải'));
    assert.equal(get('downloads').hidden,true);
    assert.equal(get('run-button').disabled,false);
  }
  const partial = await scenario({status:'incomplete',steps:[],report_id:'report'});
  assert.equal(partial.get('downloads').hidden,false);
  assert.equal(partial.get('report-title').textContent,'AI');
  console.log('Frontend error-state scenarios passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
