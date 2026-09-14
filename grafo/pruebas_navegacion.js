/* Regresión del historial del visor, sin dependencias: node grafo/pruebas_navegacion.js.
   Ejecuta las funciones reales con un DOM mínimo; no sustituye una prueba visual. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname,'src/render_html.py'),'utf8');
const elements = new Map();
for(const id of ['atras','adelante','atrasDetalle','adelanteDetalle','ruta','verCruces','der','cuerpo'])
  elements.set(id,{disabled:false,scrollTop:0,checked:false});
let sections = [];
elements.get('cuerpo').querySelectorAll = () => sections;
function render(){
  sections = ['Datos de origen','Detalle técnico de auditoría'].map(textContent=>({
    open:false,querySelector:()=>({textContent})
  }));
  elements.get('der').scrollTop = 0;
}
const ctx = vm.createContext({assert,document:{getElementById:id=>elements.get(id)},
  fichaReporte:render,fichaEntidad:render,fichaRelacion:render,fichaVinculo:render,
  fichaRevisiones:render,fichaInforme:render,fichaCaso:render,etq:id=>id,
  pintarVP(){},dibujar(){},aplicarCaso(id){vm.runInContext(`estado.caso=${JSON.stringify(id)}`,ctx);}
});
vm.runInContext(`const HIST={pila:[],pos:-1};let VP={x:12,y:34,k:.8,encuadrado:true};
  const estado={caso:'L001',raiz:'R1',centro:null,abiertos:new Set(['R1','R2']),
    mov:new Map([['R2',{dx:17,dy:21}]]),verCruces:false};`,ctx);
for(const name of ['instantanea','anotarVista','anotarDetalle','restaurarDetalle',
  'restaurarVista','ir','atras','adelante','mostrar','centrarEn','cambiarCaso']){
  const start=source.indexOf('function '+name+'(');
  assert(start>=0,name);
  vm.runInContext(source.slice(start,source.indexOf('\n}',start)+2),ctx);
}
const run=code=>vm.runInContext(code,ctx);
run(`ir({tipo:'reporte',id:'R1'});assert.equal(HIST.pos,0);`);
assert(elements.get('atrasDetalle').disabled);
sections[0].open=true;elements.get('der').scrollTop=286;
run(`VP.x=91;VP.k=1.2;ir({tipo:'relacion',id:'IP_PRESTADOR'});`);
assert.equal(elements.get('der').scrollTop,0);
assert(!elements.get('atrasDetalle').disabled);
sections[1].open=true;elements.get('der').scrollTop=110;
run(`VP.x=777;atras();assert.equal(estado.sel.id,'R1');assert.equal(VP.x,91);assert.equal(VP.k,1.2);`);
assert.equal(elements.get('der').scrollTop,286);assert(sections[0].open);assert(!sections[1].open);
assert(elements.get('atrasDetalle').disabled);assert(!elements.get('adelanteDetalle').disabled);
run(`adelante();assert.equal(estado.sel.id,'IP_PRESTADOR');assert.equal(VP.x,777);`);
assert.equal(elements.get('der').scrollTop,110);assert(sections[1].open);
// Volver restaura raíz, tarjetas desplegadas, posiciones y el interruptor.
run(`ir({tipo:'entidad',id:'IP1'});centrarEn('IP1');assert.equal(estado.centro,'IP1');
  atras();assert.equal(estado.centro,null);assert(estado.abiertos.has('R2'));
  assert.equal(estado.mov.get('R2').dx,17);assert.equal(estado.verCruces,false);
  adelante();assert.equal(estado.centro,'IP1');
  estado.verCruces=true;anotarVista();ir({tipo:'revisiones'});estado.verCruces=false;
  atras();assert.equal(estado.verCruces,true);assert(document.getElementById('verCruces').checked);
  ir({tipo:'informe'});assert.equal(HIST.pos,HIST.pila.length-1);
  const pos=HIST.pos;ir({tipo:'informe'});assert.equal(HIST.pos,pos);
  cambiarCaso('L002');assert.equal(estado.caso,'L002');atras();assert.equal(estado.caso,'L001');
  assert.equal(estado.sel.tipo,'informe');`);
// Los dos pares de botones comparten historial y handlers reales.
for(const [id,handler] of [['atrasDetalle','atras'],['adelanteDetalle','adelante']]){
  const line=`document.getElementById("${id}").onclick = ${handler};`;
  assert(source.includes(line));vm.runInContext(line,ctx);
}
elements.get('atrasDetalle').onclick();elements.get('adelanteDetalle').onclick();
assert.equal(elements.get('atras').disabled,elements.get('atrasDetalle').disabled);
assert.equal(elements.get('adelante').disabled,elements.get('adelanteDetalle').disabled);
console.log('OK: navegación lateral, Volver/Siguiente, secciones y scroll, cámara, lienzo, cambio de caso y ramas del historial.');
