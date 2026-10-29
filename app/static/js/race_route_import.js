// Сопоставление общего файла существующим этапам без автоматического разворота линий
(function () {
  const form = document.getElementById('raceImport');
  if (!form) return;
  const file = document.getElementById('raceFile');
  const rows = document.getElementById('raceMapping');
  const status = document.getElementById('raceStatus');
  const confirm = document.getElementById('confirmRace');
  const submit = form.querySelector('button[type="submit"]');
  let preview = null;
  let busy = false;
  let revision = 0;
  const base = location.pathname.replace(/\/race-route\/?$/, '/api/race-route/import/');

  function message(text, error) {
    status.textContent = text;
    status.className = error ? 'text-danger mt-2' : 'text-success mt-2';
  }
  function setBusy(value) {
    busy = value;
    file.disabled = value;
    submit.disabled = value;
    confirm.disabled = value || !preview;
  }
  function field(parent, text, element) {
    const label = document.createElement('label');
    label.className = 'd-block mb-2';
    label.append(document.createTextNode(text + ' '), element);
    parent.append(label);
    return label;
  }
  function render(lines) {
    rows.replaceChildren();
    lines.forEach(function (line, index) {
      const row = document.createElement('div');
      row.className = 'col-12 border rounded p-3';
      const title = document.createElement('h4');
      title.textContent = line.name + ' · точек: ' + line.point_count + ' · КП: ' + line.checkpoints.length;
      row.append(title);
      (line.warnings || []).forEach(function (text) {
        const warning = document.createElement('p');
        warning.className = 'text-warning'; warning.textContent = text; row.append(warning);
      });
      const stage = document.createElement('select');
      stage.className = 'form-select'; stage.required = true;
      stage.append(document.getElementById('raceStageOptions').content.cloneNode(true));
      stage.dataset.field = 'stage';
      field(row, 'Сохранить в этап', stage);
      const reverse = document.createElement('input');
      reverse.type = 'checkbox'; reverse.dataset.field = 'reverse';
      field(row, 'Развернуть порядок координат', reverse);
      const checked = document.createElement('input');
      checked.type = 'checkbox'; checked.required = true; checked.dataset.field = 'direction';
      const direction = field(row, '', checked);
      function updateDirection() {
        const first = line.points[reverse.checked ? line.points.length - 1 : 0];
        const last = line.points[reverse.checked ? 0 : line.points.length - 1];
        direction.firstChild.textContent = 'Направление проверено: [' + first.lat + ', ' + first.lon +
          '] → [' + last.lat + ', ' + last.lon + '] ';
        checked.checked = false;
      }
      updateDirection();
      reverse.addEventListener('change', updateDirection);
      line.checkpoints.forEach(function (cp) {
        const kind = document.createElement('select');
        kind.className = 'form-select'; kind.dataset.field = 'kind';
        [['checkpoint','КП'],['start','Старт'],['finish','Финиш'],['camp','Лагерь']].forEach(function (item) {
          const option = document.createElement('option'); option.value = item[0]; option.textContent = item[1]; kind.append(option);
        });
        field(row, cp.name + ' [' + cp.lat + ', ' + cp.lon + ']', kind);
      });
      row.dataset.index = index;
      rows.append(row);
      if (lines.length === 1 && form.dataset.stageId) {
        stage.value = form.dataset.stageId;
      }
    });
  }
  file.addEventListener('change', function () {
    revision += 1; preview = null; rows.replaceChildren(); confirm.disabled = true; message('', false);
    window.dispatchEvent(new CustomEvent('race-route-preview', {detail:[]}));
  });
  async function request(action, mapping) {
    const body = new FormData(); body.append('file', file.files[0]);
    if (mapping) body.append('mapping', JSON.stringify(mapping));
    const response = await fetch(base + action, {method:'POST', body:body,
      headers:{'X-Route-Import-Token':form.dataset.csrf}});
    if (response.redirected) throw new Error('Войдите в админку заново');
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Импорт не выполнен');
    return data;
  }
  form.addEventListener('submit', async function (event) {
    event.preventDefault(); if (busy || !file.files.length) return;
    const current = ++revision;
    preview = null; setBusy(true); message('Проверка файла…', false);
    try {
      const data = await request('preview');
      if (current !== revision) return;
      preview = data.lines; render(preview);
      window.dispatchEvent(new CustomEvent('race-route-preview', {detail:preview}));
      message('Предпросмотр готов, база не изменена. Проверьте этапы, направления и типы КП', false);
    } catch (error) { rows.replaceChildren(); message(error.message, true); }
    finally { setBusy(false); }
  });
  confirm.addEventListener('click', async function () {
    if (busy || !preview || !form.reportValidity()) return;
    const mapping = Array.from(rows.children).map(function (row) {
      return {stage_id:Number(row.querySelector('[data-field="stage"]').value),
        reverse:row.querySelector('[data-field="reverse"]').checked,
        direction_confirmed:row.querySelector('[data-field="direction"]').checked,
        kinds:Array.from(row.querySelectorAll('[data-field="kind"]')).map(function (e) { return e.value; })};
    });
    setBusy(true); message('Сохранение всех выбранных этапов…', false);
    try {
      await request('confirm', mapping);
      preview = null;
      message('Все выбранные этапы и КП сохранены. Обновите страницу для просмотра результата', false);
    } catch (error) { message(error.message, true); }
    finally { setBusy(false); }
  });
})();
