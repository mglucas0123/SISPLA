(function(){
  const codeInput = document.getElementById('procedure-code-input');
  const descInput = document.getElementById('surgical-description-input');
  if(!codeInput || !descInput) return;

  descInput.classList.add('bg-light');
  descInput.style.cursor = 'not-allowed';

  let container = document.createElement('div');
  container.className = 'autocomplete-suggestions list-group shadow';
  container.style.position = 'absolute';
  container.style.zIndex = '2000';
  container.style.maxHeight = '260px';
  container.style.overflowY = 'auto';
  container.style.width = '100%';
  container.style.display = 'none';
  codeInput.parentNode.style.position = 'relative';
  codeInput.parentNode.appendChild(container);

  function updateWidth(){
    const w = codeInput.offsetWidth || codeInput.getBoundingClientRect().width || (codeInput.parentElement && codeInput.parentElement.offsetWidth) || 0;
    if(w) {
      container.style.width = w + 'px';
    } else {
      container.style.width = '100%';
    }
  }

  let lastQuery = '';
  let debounceTimer = null;
  let currentIndex = -1;
  let currentItems = [];
  let selectedCode = '';
  const addBtn = document.getElementById('add-procedure-btn');
  const listWrapper = document.getElementById('procedures-list');
  const canEdit = listWrapper ? (listWrapper.getAttribute('data-can-edit-procedures') === '1') : true;
  const form = codeInput.closest('form');
  let procedures = [];

  if(listWrapper){
    const existingCodes = listWrapper.querySelectorAll('input[name="procedure_codes[]"]');
    const existingDescs = listWrapper.querySelectorAll('input[name="procedure_descriptions[]"]');
    if(existingCodes.length){
      procedures = Array.from(existingCodes).map((inp, idx)=>({
        code: inp.value.trim(),
        description: existingDescs[idx] ? existingDescs[idx].value.trim() : ''
      }));
      renderProcedures();
    }
  }

  function debounce(fn, delay){
    return function(...args){
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(()=>fn.apply(this,args), delay);
    };
  }

  function fetchSuggestions(q){
    if(!q || q.length < 1){
      hide();
      return;
    }
    if(q === lastQuery) return;
    lastQuery = q;
    fetch(`/nir/procedures/search?q=${encodeURIComponent(q)}`)
      .then(r=>r.json())
      .then(data=>{
        currentItems = data || [];
        render();
      })
      .catch(()=>{  });
  }

  function render(){
    container.innerHTML = '';
    currentIndex = -1;
    if(!currentItems.length){ hide(); return; }
    currentItems.forEach((item, idx)=>{
      const a = document.createElement('button');
      a.type = 'button';
      a.className = 'list-group-item list-group-item-action py-1';
      a.style.fontSize = '0.85rem';
      a.innerHTML = `<strong>${item.code}</strong> - ${escapeHtml(item.description)}`;
      a.addEventListener('click', ()=>select(idx));
      container.appendChild(a);
    });
    show();
  }

  function select(idx){
    const item = currentItems[idx];
    if(!item) return;
    codeInput.value = item.code;
    descInput.value = item.description;
    selectedCode = item.code;
    hide();
  }

  function addCurrent(){
    if(!canEdit) return;
    const c = codeInput.value.trim();
    const d = descInput.value.trim();
    if(!c || !d) return;
    if(procedures.some(p=>p.code === c)){
      codeInput.classList.add('is-invalid');
      setTimeout(()=>codeInput.classList.remove('is-invalid'),1500);
      return;
    }
    procedures.push({code:c, description:d});
    renderProcedures();
    codeInput.value = '';
    descInput.value = '';
    selectedCode='';
  }

  function removeProcedure(index){
    if(!canEdit) return;
    procedures.splice(index,1);
    renderProcedures();
  }

  function renderProcedures(){
    if(!listWrapper) return;
    listWrapper.innerHTML = '';
    procedures.forEach((p,i)=>{
      const row = document.createElement('div');
      row.className = 'd-flex align-items-start gap-2 mb-1';
      let btnHtml = '';
      if(canEdit){
        btnHtml = `<button type="button" class="btn btn-sm btn-outline-danger" aria-label="Remover" data-index="${i}">&times;</button>`;
      }
      row.innerHTML = `
        <div class="flex-grow-1 small border rounded p-2 bg-white">
          <strong>${escapeHtml(p.code)}</strong><br>
          <span class="text-muted">${escapeHtml(p.description)}</span>
        </div>
        ${btnHtml}
        <input type="hidden" name="procedure_codes[]" value="${escapeHtml(p.code)}">
        <input type="hidden" name="procedure_descriptions[]" value="${escapeHtml(p.description)}">
      `;
      listWrapper.appendChild(row);
    });
  }

  function show(){
    updateWidth();
    container.style.display = 'block';
  }
  function hide(){
    container.style.display = 'none';
  }

  function escapeHtml(str){
    return (str||'').replace(/[&<>"']/g, c=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;' }[c]));
  }

  const debouncedFetch = debounce(fetchSuggestions, 250);

  codeInput.addEventListener('input', e=>{
    const val = e.target.value.trim();
    if(val === '' || (selectedCode && val !== selectedCode)){
      descInput.value = '';
      selectedCode = '';
    }
    debouncedFetch(val);
  });

  codeInput.addEventListener('keydown', e=>{
    if(container.style.display === 'none') return;
    const max = currentItems.length -1;
    if(e.key === 'ArrowDown'){
      e.preventDefault();
      currentIndex = currentIndex < max ? currentIndex +1 : 0;
      highlight();
    } else if(e.key === 'ArrowUp') {
      e.preventDefault();
      currentIndex = currentIndex > 0 ? currentIndex -1 : max;
      highlight();
    } else if(e.key === 'Enter') {
      if(currentIndex >=0){
        e.preventDefault();
        select(currentIndex);
      }
    } else if(e.key === 'Escape') {
      hide();
    }
  });

  document.addEventListener('click', (e)=>{
    if(!container.contains(e.target) && e.target !== codeInput){
      hide();
    }
    if(canEdit && e.target.matches('button[data-index]')){
      const idx = parseInt(e.target.getAttribute('data-index')); 
      if(!isNaN(idx)) removeProcedure(idx);
    }
  });

  function highlight(){
    [...container.children].forEach((el, i)=>{
      if(i === currentIndex){
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
    });
  }
  descInput.addEventListener('focus', ()=>{
    codeInput.focus();
  });

  window.addEventListener('resize', updateWidth);
  codeInput.addEventListener('focus', updateWidth);

  if(addBtn && canEdit){
    addBtn.addEventListener('click', (e)=>{
      e.preventDefault();
      addCurrent();
    });
  }

  if(form){
    form.addEventListener('submit', ()=>{
      if(procedures.length){
        let legacyCode = form.querySelector('input[name="procedure_code"]');
        let legacyDesc = form.querySelector('input[name="surgical_description"]');
        if(legacyCode) legacyCode.value = procedures[0].code;
        if(legacyDesc) legacyDesc.value = procedures[0].description;
      }
    });
  }
})();
