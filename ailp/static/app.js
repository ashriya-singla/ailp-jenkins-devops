'use strict';
let currentPassport = null;
const message = document.getElementById('message');
async function api(path, method = 'GET', body) {
  const response = await fetch(path, {method, headers: {
    'Authorization': `Bearer ${document.getElementById('token').value}`,
    'Content-Type': 'application/json'
  }, body: body ? JSON.stringify(body) : undefined});
  if (response.status === 204) return null;
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
function renderRecords(target, records, editable = false) {
  const parent = document.getElementById(target);
  parent.replaceChildren();
  if (!records.length) parent.textContent = 'No evidence imported yet.';
  records.forEach(record => {
    const card = document.createElement('article');
    [['Evidence', record.id], ['Source', record.source], ['Prompt', record.prompt],
     ['AI response', record.response], ['Decision', record.decision || 'Pending'],
     ['Reflection', record.reasoning || 'Pending']].forEach(([label, value]) => {
      const p = document.createElement('p');
      p.textContent = `${label}: ${value}`;
      card.appendChild(p);
    });
    if (editable) {
      const note = document.createElement('button'); note.textContent = 'Add decision';
      note.onclick = () => {document.querySelector('#decision-form [name=id]').value = record.id; show('decision');};
      const remove = document.createElement('button'); remove.textContent = 'Delete record';
      remove.onclick = () => action(async () => {
        if (window.confirm('Delete this demonstration evidence record?')) {
          await api(`/api/evidence/${record.id}`, 'DELETE'); await show('timeline');
        }
      });
      card.append(note, remove);
    }
    parent.appendChild(card);
  });
}
async function action(fn) {
  message.textContent = '';
  try {await fn();} catch (error) {message.textContent = error.message;}
}
async function show(screen) {
  document.querySelectorAll('main section').forEach(el => {el.hidden = el.id !== screen;});
  await action(async () => {
    if (screen === 'timeline') renderRecords('records', await api('/api/evidence'), true);
    if (screen === 'passport' || screen === 'educator') {
      currentPassport = await api('/api/passport');
      renderRecords(`${screen}-records`, currentPassport.evidence);
    }
    if (screen === 'privacy') {
      const result = await api('/api/privacy');
      document.getElementById('privacy-state').textContent = result.shared ? 'Educator access granted' : 'Private';
    }
  });
}
document.querySelectorAll('[data-screen]').forEach(button => {button.onclick = () => show(button.dataset.screen);});
document.getElementById('import-form').onsubmit = event => {
  event.preventDefault(); action(async () => {
    const data = Object.fromEntries(new FormData(event.target)); data.consent = data.consent === 'on';
    await api('/api/evidence', 'POST', data); event.target.reset(); await show('timeline');
  });
};
document.getElementById('decision-form').onsubmit = event => {
  event.preventDefault(); action(async () => {
    const data = Object.fromEntries(new FormData(event.target));
    await api(`/api/evidence/${data.id}/decision`, 'PUT', data); await show('timeline');
  });
};
['share','revoke'].forEach(id => {document.getElementById(id).onclick = () => action(async () => {
  await api('/api/privacy', 'PUT', {shared: id === 'share'}); await show('privacy');
});});
document.getElementById('export').onclick = () => {
  if (!currentPassport) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(currentPassport, null, 2)], {type:'application/json'}));
  const link = document.createElement('a'); link.href = url; link.download = 'AILP_Passport.json'; link.click();
  URL.revokeObjectURL(url);
};
