// Exercise the actual client module with a worker whose cancelled job never settles.
import assert from "node:assert/strict";

class Element {
    constructor() {this.value=""; this.disabled=false; this.hidden=false; this.dataset={}; this.children=[]; this.listeners={}; this.attributes={}; this.textContent="";}
    addEventListener(name, callback) {this.listeners[name]=callback;}
    emit(name) {return this.listeners[name]?.({preventDefault(){}});}
    replaceChildren() {this.children=[];}
    append(child) {this.children.push(child);}
    querySelectorAll() {return this.children;}
    setAttribute(name,value) {this.attributes[name]=value;}
    removeAttribute(name) {delete this.attributes[name];}
    getBoundingClientRect() {return {top:0,height:100};}
    focus() {}
}
const elements=new Map();
globalThis.document={getElementById:id=>{
    if (!elements.has(id)) elements.set(id,new Element());
    return elements.get(id);
},createElement:()=>new Element(),querySelector:()=>new Element()};
const listeners={};
globalThis.window={scrollY:0,scrollTo(){},addEventListener(name,callback){listeners[name]=callback;}};
globalThis.getComputedStyle=()=>({position:"static"});
const element=id=>document.getElementById(id);
element("book-reader").dataset.total="12";
element("book-ocr").dataset={statusUrl:"https://fixture.example/ocr",csrf:"fixture-only"};
element("ocr-language").value="chi_sim";
let calls=0, terminated=0;
globalThis.ocrTestFactoryCalls=0;
globalThis.ocrTestWorker={
    async setParameters(){},
    recognize(){calls++; return calls===1 ? Promise.resolve({data:{text:"page eight text",confidence:90}}) : new Promise(()=>{});},
    async terminate(){terminated++;},
};
const writes=[];
globalThis.fetch=async (url,options={})=>{
    let value;
    if (options.method==="POST") {
        const fields=Object.fromEntries(options.body);
        writes.push(fields);
        value={status:"saved",page:Number(fields.page),text:fields.text,preview_url:"/page-eight"};
    } else {
        value={page:Number(new URL(url).searchParams.get("page")),state:"missing",digest:"fixture-digest"};
    }
    return {ok:true,status:200,redirected:false,headers:{get:()=>"application/json"},json:async()=>value};
};
const {initBookOCR}=await import(process.argv[2]);
initBookOCR({getCurrentPage:()=>8,jump(){},renderForOCR:async()=>Object.assign(new Element(),{width:100,height:100})});
element("ocr-range-start").value="8";
element("ocr-range-end").value="10";
element("ocr-range-form").emit("submit");
async function until(predicate) {
    const deadline=Date.now()+2000;
    while (!predicate()) {
        assert.ok(Date.now()<deadline,"client operation did not settle after cancellation");
        await new Promise(resolve=>setTimeout(resolve,1));
    }
}
await until(()=>calls===2);
element("ocr-cancel").emit("click");
await until(()=>!element("ocr-text").disabled);
assert.equal(element("ocr-text").value,"page eight text");
assert.equal(element("ocr-save").disabled,false);
assert.match(element("ocr-status").textContent,/已取消本批识别/);
assert.equal(globalThis.ocrTestFactoryCalls,1,"the batch should reuse one worker");
assert.equal(terminated,1);
assert.equal(writes.length,0,"recognition and cancellation must not approve any page");
assert.deepEqual(element("ocr-results").children.map(button=>button.textContent),["第8页 · 待核对","第9页 · 未处理","第10页 · 未处理"]);
let prevented=false;
listeners.beforeunload({preventDefault(){prevented=true;}});
assert.equal(prevented,true,"unapproved results must be protected from accidental navigation");
element("ocr-text").value="page eight reviewed and corrected";
element("ocr-text").emit("input");
await element("ocr-save").emit("click");
assert.equal(writes.length,1);
assert.equal(writes[0].page,"8");
assert.equal(writes[0].text,"page eight reviewed and corrected");
assert.equal(element("ocr-results").children[0].textContent,"第8页 · 已保存");
assert.equal(element("ocr-results").children[1].textContent,"第9页 · 未处理");
assert.equal(element("ocr-range-go").disabled,false,"a new batch is allowed after all completed drafts are approved");
console.log("Cancellation preserves completed drafts and single-page approval; one worker reused.");
