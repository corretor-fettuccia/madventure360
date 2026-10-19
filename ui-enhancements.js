// Presentation only. Existing stitching, metadata and export handlers are unchanged.
(()=>{
  const sides=document.querySelectorAll('.shell > aside');
  if(sides.length!==2)return;
  const advanced=sides[1];
  const groups=Array.from(advanced.children).filter(el=>el.matches('section'));
  const labels=['Calibração das lentes','Ajustes da visualização','Resolução e exportação'];
  const container=document.createElement('div');container.className='ui-panels';
  groups.forEach((section,i)=>{
    const fold=document.createElement('details');fold.className='ui-fold';
    if(i===0 || i===2)fold.open=true;
    const summary=document.createElement('summary');summary.textContent=labels[i]||'Outros ajustes';
    fold.append(summary,section);container.append(fold);
  });advanced.append(container);
  const workflow=document.createElement('div');workflow.className='workflow';workflow.setAttribute('aria-label','Fluxo de trabalho');
  workflow.innerHTML='<span>1. Adicionar arquivos</span><span class="arrow">→</span><span>2. Calibrar</span><span class="arrow">→</span><span>3. Exportar 360°</span>';
  const main=document.querySelector('.shell > main');main?.querySelector('.topline')?.after(workflow);
  const drop=document.getElementById('drop');if(drop){drop.tabIndex=0;drop.setAttribute('role','button');drop.setAttribute('aria-label','Selecionar imagens e vídeos para importar');drop.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();document.getElementById('file')?.click();}})}
  for(const id of ['batchStatus','calStatus','message']){let node=document.getElementById(id);if(node){node.setAttribute('role','status');node.setAttribute('aria-live','polite')}}
  const export2=document.getElementById('export2');if(export2)export2.textContent='Exportar panorama 360°';
  const hint=document.createElement('p');hint.className='ui-helper';hint.textContent='O processamento é local; seus arquivos não são enviados à internet.';
  document.getElementById('batchStatus')?.after(hint);
  document.title='Madventure Web Studio 0.8 · Editor 360°';
  const empty=document.querySelector('.empty h2');if(empty)empty.textContent='Seu editor 360° está pronto';
})();
