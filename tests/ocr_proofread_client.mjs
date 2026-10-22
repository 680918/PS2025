// Drive the real OCR module: delayed and failed source images must not mislabel a draft.
import assert from "node:assert/strict";

class Element {
    constructor() {this.value=""; this.disabled=false; this.hidden=false; this.dataset={}; this.children=[]; this.listeners={}; this.attributes={}; this.textContent="";}
    addEventListener(name, callback) {this.listeners[name]=callback;}
    emit(name) {return this.listeners[name]?.({preventDefault(){}});}
    replaceChildren(...children) {this.children=children;}
    append(child) {this.children.push(child);}
    querySelectorAll() {return this.children;}
    setAttribute(name,value) {this.attributes[name]=value;}
    removeAttribute(name) {delete this.attributes[name];}
    getBoundingClientRect() {return {top:0,height:100};}
    focus() {}
}
const elements=new Map(), listeners={};
globalThis.document={getElementById:id=>{
    if (!elements.has(id)) elements.set(id,new Element());
    return elements.get(id);
},createElement:()=>new Element(),querySelector:()=>new Element()};
globalThis.window={scrollY:0,scrollTo(){},addEventListener(name,callback){listeners[name]=callback;}};
globalThis.getComputedStyle=()=>({position:"static"});
const element=id=>document.getElementById(id);
element("book-reader").dataset.total="12";
element("book-ocr").dataset={statusUrl:"https://fixture.example/ocr",csrf:"fixture-only"};
element("ocr-language").value="chi_sim";
const writes=[], sourceJobs=[];
let recognized=0, terminated=0, jumps=0;
globalThis.ocrTestFactoryCalls=0;
globalThis.ocrTestWorker={async setParameters(){},async recognize(){return {data:{text:"draft "+(++recognized),confidence:90}};},async terminate(){terminated++;}};
globalThis.fetch=async (url,options={})=>{
    const fields=options.method==="POST" ? Object.fromEntries(options.body) : null;
    if (fields) writes.push(fields);
    const value=fields ? {status:"saved",page:Number(fields.page),text:fields.text,preview_url:"/saved-six"} : {page:Number(new URL(url).searchParams.get("page")),state:"missing",digest:"fixture-digest"};
    return {ok:true,status:200,redirected:false,headers:{get:()=>"application/json"},json:async()=>value};
};
const {initBookOCR}=await import(process.argv[2]);
initBookOCR({getCurrentPage:()=>8,jump(){jumps++;},renderForOCR:(page,width)=>{
    const canvas=Object.assign(new Element(),{width:1400,height:1960,page});
    if (width!==1400) return Promise.resolve(canvas);
    assert.equal(terminated,1,"preview starts after OCR has released its worker");
    return new Promise((resolve,reject)=>sourceJobs.push({page,canvas,resolve:()=>resolve(canvas),reject}));
}});
async function until(predicate) {
    const deadline=Date.now()+2000;
    while (!predicate()) {
        assert.ok(Date.now()<deadline,"proofreading operation did not settle");
        await new Promise(resolve=>setTimeout(resolve,1));
    }
}
element("ocr-range-start").value="5"; element("ocr-range-end").value="7";
element("ocr-range-form").emit("submit");
await until(()=>sourceJobs.length===1);
assert.equal(recognized,3); assert.equal(writes.length,0);
assert.equal(sourceJobs[0].page,5);
element("ocr-text").value="corrected page five"; element("ocr-text").emit("input");
element("ocr-results").children[1].emit("click");
element("ocr-results").children[2].emit("click");
assert.equal(sourceJobs.length,1,"fast switches must not start parallel source renders");
sourceJobs[0].resolve();
await until(()=>sourceJobs.length===2);
assert.equal(sourceJobs[0].canvas.width,0,"late page-five image must be discarded");
assert.equal(sourceJobs[1].page,7,"only the latest selection is queued");
assert.equal(element("ocr-source-frame").children.length,0,"do not show another page while loading");
sourceJobs[1].resolve();
await until(()=>element("ocr-source-frame").children.length===1);
assert.equal(element("ocr-source-frame").children[0].page,7);
assert.equal(element("ocr-source-frame").children[0].attributes["aria-label"],"PDF 文件第 7 页对照原图");
assert.match(element("ocr-result-label").textContent,/第 7 页/);
element("ocr-source-zoom").value="200"; element("ocr-source-zoom").emit("change");
assert.equal(element("ocr-source-frame").dataset.zoom,"200");
assert.equal(sourceJobs.length,2,"zoom reuses the current image");
element("ocr-results").children[1].emit("click");
await until(()=>sourceJobs.length===3);
assert.equal(sourceJobs[1].canvas.width,0,"previous image memory should be released");
sourceJobs[2].reject(new Error("fixture render failed"));
await until(()=>!element("ocr-source-retry").hidden);
assert.equal(element("ocr-text").value,"draft 2");
assert.equal(element("ocr-save").disabled,false,"image failure must not erase or lock the text");
assert.equal(element("ocr-source-frame").children.length,0);
element("ocr-source-retry").emit("click");
await until(()=>sourceJobs.length===4);
sourceJobs[3].resolve();
await until(()=>element("ocr-source-frame").children.length===1);
assert.equal(element("ocr-source-frame").children[0].page,6);
element("ocr-text").value="corrected page six"; element("ocr-text").emit("input");
await element("ocr-save").emit("click");
assert.deepEqual(writes.map(fields=>[fields.page,fields.text]),[["6","corrected page six"]]);
element("ocr-results").children[0].emit("click");
await until(()=>sourceJobs.length===5);
assert.equal(element("ocr-text").value,"corrected page five","switching retains each unapproved draft");
element("ocr-source-toggle").emit("click");
sourceJobs[4].resolve();
await until(()=>sourceJobs[4].canvas.width===0);
assert.equal(element("ocr-source-pane").hidden,true);
assert.equal(element("ocr-source-toggle").attributes["aria-expanded"],"false");
element("ocr-source-toggle").emit("click");
await until(()=>sourceJobs.length===6);
sourceJobs[5].resolve();
await until(()=>element("ocr-source-frame").children.length===1);
assert.equal(element("ocr-source-frame").children[0].page,5);
assert.equal(jumps,0,"proofreading must not change the full-book reading position");
assert.equal(writes.length,1,"image browsing must not approve other pages");
listeners.pagehide({});
assert.equal(sourceJobs[5].canvas.width,0);
assert.equal(element("ocr-source-frame").children.length,0);
console.log("Source and draft stay aligned; stale images released, retry safe, one-page save only.");
