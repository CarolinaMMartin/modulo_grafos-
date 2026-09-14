const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const source = fs.readFileSync(process.argv[2]||require('path').join(__dirname,'src/render_html.py'),'utf8');
function fn(name){
  const i=source.indexOf('function '+name+'(');
  assert(i>=0,name);
  return source.slice(i, source.indexOf('\n}',i)+2);
}
class Element {
  constructor(tag){ this.tag=tag; this.attrs={}; this.children=[]; this.listeners={}; this.style={}; this.textContent='';
    this.classList={
      add: (value)=> { const set=new Set((this.attrs.class||'').split(' ').filter(Boolean));set.add(value);this.attrs.class=[...set].join(' '); },
      toggle: (value,on)=> {const set=new Set((this.attrs.class||'').split(' ').filter(Boolean));if(on)set.add(value);else set.delete(value);this.attrs.class=[...set].join(' ');},
      contains:value=>(this.attrs.class||'').split(' ').includes(value)
    };
  }
  setAttribute(k,v){ this.attrs[k]=String(v); }
  getAttribute(k){ return this.attrs[k]; }
  appendChild(e){this.children.push(e);e.parent=this;}
  removeChild(e){ this.children=this.children.filter(x=>x!==e); }
  addEventListener(k,fn){ (this.listeners[k]??=[]).push(fn); }
  getComputedTextLength(){return this.textContent.length*5;}
  querySelectorAll(selector){ const key=selector.slice(1,-1); const out=[]; const visit=e=>e.children.forEach(c=>{if(key in c.attrs)out.push(c);visit(c);});visit(this);return out; }
  emit(kind,extra={}){const e={stopped:false,prevented:false,stopPropagation(){this.stopped=true;},preventDefault(){this.prevented=true;},...extra};for(const fn of this.listeners[kind]||[])fn(e);if(!e.stopped&&this.parent) for(const fn of this.parent.listeners[kind]||[])fn(e);return e;}
}
const fields=new Map(['verCruces','atras','adelante','ruta'].map(x=>[x,{checked:false,disabled:false,textContent:''}]));
fields.set('der',{scrollTop:0});fields.set('cuerpo',{querySelectorAll:()=>[]});
const ctx=vm.createContext({console, Element,document:{createElementNS:(_ns,tag)=>new Element(tag),getElementById:id=>fields.get(id)},assert});
vm.runInContext(`const SVGNS='svg',ANCHO_CAJA=250,ALTO_CAJA=64; const MEDIDAS=new Map(); let SEARRASTRO=false; const gCaj=new Element('g'); const HIST={pila:[],pos:-1}; let VP={encuadrado:true}; const estado={caso:'L001',raiz:'R1',centro:null,abiertos:new Set(['R1','R2']),mov:new Map([['R1',{dx:8,dy:4}]]),verCruces:true}; const D={aristas:[]}; const NODOS=new Map(); const RELACIONES_EN_TARJETA={ASIGNADA_A:true}; function reportesCaso(){return new Set(['R1','R2','R3']);} function aplicarCaso(id){estado.caso=id;} function mostrar(v){estado.sel=v;} function pintarVP(){}`,ctx);
for(const name of ['medir','ajustar','caja','otrosReportesDe','detallesDe','marcarAlcance','instantanea','anotarVista','anotarDetalle','restaurarDetalle','restaurarVista','ir','atras','adelante','centrarEn'])vm.runInContext(fn(name),ctx);
vm.runInContext(`
for(const titulo of ['cuenta breve','nombre de cuenta demasiado largo que requiere un punto']){
  let cajaClicks=0,marcaClicks=0,drag=0;
  const el=caja(gCaj,0,0,{titulo,sub:'Cuenta',marca:'en 3 reportes ›',alClic:()=>cajaClicks++,alClicMarca:()=>marcaClicks++,ayudaMarca:'Centrar la cuenta'});
  const m=el.children.find(n=>n.classList.contains('accion')); assert(m);
  assert.equal(m.getAttribute('role'),'button'); assert.equal(m.getAttribute('tabindex'),'0');
  assert.equal(m.getAttribute('aria-label'),'Centrar la cuenta'); assert(m.children.some(c=>c.tag==='title'));
  el.addEventListener('pointerdown',()=>drag++);
  assert(m.emit('pointerdown').stopped);assert(m.emit('click').stopped);
  assert(m.emit('keydown',{key:'Enter'}).stopped);assert(m.emit('keydown',{key:' '}).prevented);
  assert.equal(marcaClicks,3);assert.equal(cajaClicks,0);assert.equal(drag,0);
  assert.equal(m.tag,titulo==='cuenta breve'?'text':'circle');
}
const reps=['R1','R2','R3','R4'].map(r=>{const e=new Element('g');e.setAttribute('data-reporte',r);gCaj.appendChild(e);return e;});
marcarAlcance({reportes:['R1','R2','R3','R5']},true);
assert(reps.slice(0,3).every(e=>e.classList.contains('alcance')));assert(reps[3].classList.contains('fuera'));
marcarAlcance({reportes:['R1','R2','R3']},false);assert(reps.every(e=>!e.classList.contains('alcance')&&!e.classList.contains('fuera')));
D.aristas=[{a:'IP1',b:'ISP1',relacion:'ASIGNADA_A',vigente:true},{a:'IP1',b:'ISP1',relacion:'ASIGNADA_A'}, {a:'IP1',b:'ISP2',relacion:'ASIGNADA_A',vigente:false},{a:'IP1',b:'ISP3',relacion:'ASIGNADA_A',estado:'rechazada'},{a:'IP1',b:'GEO1',relacion:'GEOLOCALIZA_EN'}];
for(const [id,etiqueta] of [['ISP1','TeleCentro'],['ISP2','Anterior'],['ISP3','Rechazado'],['GEO1','Ciudad']])NODOS.set(id,{etiqueta});
assert.equal(detallesDe('IP1').join(', '),'TeleCentro');
ir({tipo:'entidad',id:'CUENTA1'});
assert.equal(HIST.pos,0);
centrarEn('CUENTA1');assert.equal(HIST.pos,1);assert.equal(estado.centro,'CUENTA1');assert.equal(estado.abiertos.size,0);
atras();assert.equal(estado.centro,null);assert(estado.abiertos.has('R1'));assert.equal(estado.mov.get('R1').dx,8);assert.equal(estado.verCruces,true);assert.equal(document.getElementById('verCruces').checked,true);
adelante();assert.equal(estado.centro,'CUENTA1');assert.equal(HIST.pos,1);
centrarEn('CUENTA1');assert.equal(HIST.pos,1);
estado.verCruces=false;anotarVista();centrarEn('CUENTA2');assert.equal(HIST.pos,2);
atras();assert.equal(estado.centro,'CUENTA1');assert.equal(estado.verCruces,false);assert.equal(document.getElementById('verCruces').checked,false);
console.log('OK: marca textual y punto, clic y teclado, sin drag/selección, alcance y limpieza, proveedor vigente sin duplicados, Volver/Adelante con misma entidad y cruces.');
`,ctx);
