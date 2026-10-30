const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const template = fs.readFileSync(path.join(root, 'app/templates/sqladmin/race_route.html'), 'utf8');
const fullScript = fs.readFileSync(path.join(root, 'app/static/js/race_route_import.js'), 'utf8');
const mapScript = [...template.matchAll(/<script>([\s\S]*?)<\/script>/g)][0][1];
const lines = [{
  name: 'Трасса', point_count: 2, warnings: [],
  points: [{lat: 53, lon: 158}, {lat: 54, lon: 159}],
  checkpoints: [{name: '<КП>', lat: 53.5, lon: 158.5, kind: 'checkpoint'}],
}];

// Минимальный DOM сохраняет элементы и исполняет настоящие обработчики страницы
class Element {
  constructor(tag = 'div', attrs = {}) {
    this.tag = tag; this.children = []; this.dataset = {}; this.listeners = {};
    this.disabled = false; this.checked = false; this.value = ''; this.attrs = attrs;
    this.textContent = ''; this.classList = {add() {}, remove() {}};
  }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  get firstChild() { return this.children[0]; }
  get innerHTML() { return this.textContent.replaceAll('<', '&lt;').replaceAll('>', '&gt;'); }
  set innerHTML(value) { this.textContent = value; this.children = []; }
  getAttribute(name) { return this.attrs[name]; }
  setAttribute(name, value) { this.attrs[name] = value; }
  addEventListener(type, listener) { (this.listeners[type] ||= []).push(listener); }
  async emit(type) {
    if (this.disabled) return;
    for (const listener of this.listeners[type] || []) await listener({preventDefault() {}});
  }
  click() { return this.emit('click'); }
  querySelectorAll(selector) {
    const field = selector.match(/^\[data-field="(.+)"\]$/)?.[1];
    return this.children.flatMap(child => child instanceof Element
      ? [...(child.dataset.field === field ? [child] : []), ...child.querySelectorAll(selector)] : []);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

function browser() {
  const elements = {};
  for (const [, tag, attrs, id] of template.matchAll(/<(\w+)([^>]*?\sid="([^"]+)"[^>]*)>/g)) {
    const element = elements[id] = new Element(tag);
    element.disabled = /\bdisabled\b/.test(attrs);
    element.type = attrs.match(/\btype="([^"]+)"/)?.[1];
  }
  const submit = new Element('button');
  elements.raceImport.querySelector = () => submit;
  elements.raceImport.dataset = {csrf: 'token', stageId: '1'};
  elements.raceImport.reportValidity = () => true;
  elements.routeImport.dataset.csrf = 'token';
  elements.importStage.value = '1';
  elements.raceFile.files = [{name: 'full.kml', size: 100}];
  elements.routeFile.files = [{name: 'line.gpx', size: 100}];
  elements.raceStageOptions.content = {cloneNode: () => new Element('option')};
  const stages = ['1', '2'].map(id => new Element('button', {
    'data-stage-id': id, 'data-route': '[{"lat":51,"lon":156},{"lat":52,"lon":157}]',
    'data-checkpoints': '[]',
  }));
  const document = {
    getElementById: id => elements[id] || null,
    createElement: tag => new Element(tag),
    createTextNode: text => ({textContent: text}),
    querySelectorAll: () => stages,
    querySelector: selector => stages.find(btn => selector.includes('"' + btn.attrs['data-stage-id'] + '"')),
  };
  const events = {};
  const window = {
    location: {pathname: '/admin/race-route'},
    addEventListener(type, fn) { (events[type] ||= []).push(fn); },
    dispatchEvent(event) { for (const fn of events[event.type] || []) fn(event); },
  };
  class Collection {
    constructor() { this.objects = new Set(); }
    add(object) { this.objects.add(object); }
    remove(object) { this.objects.delete(object); }
    getBounds() {
      const coords = [...this.objects].flatMap(object => Array.isArray(object.coords[0])
        ? object.coords : [object.coords]);
      return [[Math.min(...coords.map(p => p[0])), Math.min(...coords.map(p => p[1]))],
        [Math.max(...coords.map(p => p[0])), Math.max(...coords.map(p => p[1]))]];
    }
  }
  class Polyline {
    constructor(coords) { this.coords = coords; this.geometry = {getBounds: () => coords}; }
  }
  class Placemark { constructor(coords, props) { this.coords = coords; this.props = props; } }
  let ready;
  const map = {geoObjects: new Collection(), bounds: [], setBounds(bounds) { this.bounds.push(bounds); }};
  const requests = [];
  let responder = url => url.includes('/api/race-route/import/') ? {lines} : {stage_id: 1, points: lines[0].points};
  const context = vm.createContext({
    document, window, location: window.location,
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
    FormData: class { constructor() { this.fields = {}; } append(key, value) { this.fields[key] = value; } },
    fetch: async (url, options) => {
      requests.push({url, options});
      const data = await responder(url);
      return {ok: true, redirected: false, json: async () => data};
    },
    ymaps: {ready(fn) { ready = fn; }, Map: function () { return map; },
      GeoObjectCollection: Collection, Polyline, Placemark},
    console,
  });
  vm.runInContext(fullScript, context, {filename: 'race_route_import.js'});
  vm.runInContext(mapScript, context, {filename: 'race_route.html'});
  return {elements, stages, requests, map, ready: () => ready(),
    respond: fn => { responder = fn; },
    fullLayer: () => [...map.geoObjects.objects].find(obj => obj instanceof Collection &&
      [...obj.objects].some(item => item instanceof Placemark)),
    lineLayer: () => [...map.geoObjects.objects].find(obj => obj instanceof Polyline && obj.coords[0][0] === 53),
  };
}

async function parseFull(b) { await b.elements.raceImport.emit('submit'); }

// Общий слой или очистка при смене этапа снова сломают этот сценарий
test('полный preview остаётся на карте после клика по этапу и смены select', async () => {
  const b = browser(); b.ready(); await parseFull(b);
  const full = b.fullLayer(); assert.ok(full);
  await b.stages[1].click();
  assert.ok(b.map.geoObjects.objects.has(full), 'клик этапа удалил полный preview');
  b.elements.importStage.value = '1'; await b.elements.importStage.emit('change');
  assert.ok(b.map.geoObjects.objects.has(full), 'смена этапа удалила полный preview');
  assert.equal(b.elements.confirmRace.disabled, false);
  assert.equal(b.requests.length, 1);
  assert.match(b.requests[0].url, /\/import\/preview$/);
  assert.equal(b.stages[1].getAttribute('data-route'), '[{"lat":51,"lon":156},{"lat":52,"lon":157}]');
});

test('явный показ возвращает геометрию без fetch и сброса mapping', async () => {
  const b = browser(); b.ready(); await parseFull(b);
  const full = b.fullLayer();
  const row = b.elements.raceMapping.children[0];
  row.querySelector('[data-field="stage"]').value = '2';
  const reverse = row.querySelector('[data-field="reverse"]');
  reverse.checked = true; await reverse.emit('change');
  row.querySelector('[data-field="direction"]').checked = true;
  row.querySelector('[data-field="kind"]').value = 'camp';
  await b.stages[1].click();
  const show = b.elements.showRacePreview;
  assert.ok(show, 'нужна явная кнопка показа'); assert.equal(show.type, 'button');
  assert.equal(show.disabled, false);
  await show.click(); await show.click();
  assert.equal(b.requests.length, 1, 'повторный показ не обращается к серверу');
  assert.equal(b.elements.raceMapping.children[0], row, 'mapping не пересоздаётся');
  assert.equal(b.fullLayer(), full, 'полный слой не пересоздаётся');
  assert.equal([...b.map.geoObjects.objects].filter(obj => obj === full).length, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(b.map.bounds.at(-1))), [[53,158],[54,159]]);
  await b.elements.confirmRace.click();
  assert.equal(b.requests.length, 2);
  assert.match(b.requests[1].url, /\/confirm$/);
  assert.deepEqual(JSON.parse(b.requests[1].options.body.fields.mapping), [{
    stage_id: 2, reverse: true, direction_confirmed: true, kinds: ['camp'],
  }]);
});

test('полный preview до ready сохраняется и отображается после готовности карты', async () => {
  const b = browser();
  b.respond(() => ({lines: [...lines, {
    name: 'Второй этап', point_count: 2, warnings: [], checkpoints: [],
    points: [{lat: 54, lon: 159}, {lat: 55, lon: 160}],
  }]}));
  await parseFull(b);
  assert.equal(b.elements.raceMapping.children.length, 2);
  await b.elements.showRacePreview.click();
  b.ready();
  const full = b.fullLayer();
  assert.ok(full, 'полученный до ready preview потерян');
  const objects = [...full.objects];
  assert.equal(objects.length, 3);
  assert.deepEqual(JSON.parse(JSON.stringify(objects[0].coords)), [[53,158],[54,159]]);
  assert.equal(objects[1].props.hintContent, '&lt;КП&gt;');
  assert.deepEqual(JSON.parse(JSON.stringify(objects[2].coords)), [[54,159],[55,160]]);
  assert.deepEqual(JSON.parse(JSON.stringify(b.map.bounds.at(-1))), [[53,158],[55,160]]);
  assert.equal(b.requests.length, 1);
});

test('предпросмотр линии и полный preview не удаляют друг друга', async () => {
  const b = browser(); b.ready();
  await b.elements.routeImport.emit('submit');
  const line = b.lineLayer(); assert.ok(line);
  await parseFull(b);
  assert.ok(b.map.geoObjects.objects.has(line), 'полный preview удалил preview линии');
  const full = b.fullLayer(); assert.ok(full);
  await b.elements.routeFile.emit('change');
  assert.ok(b.map.geoObjects.objects.has(full), 'смена файла линии удалила полный preview');
  await b.elements.routeImport.emit('submit');
  const nextLine = b.lineLayer(); assert.ok(nextLine);
  await b.elements.raceFile.emit('change');
  assert.equal(b.fullLayer(), undefined);
  assert.ok(b.map.geoObjects.objects.has(nextLine), 'смена полного файла удалила preview линии');
  assert.equal(b.elements.confirmRoute.disabled, false);
  assert.equal(b.elements.confirmRace.disabled, true);
  assert.equal(b.elements.showRacePreview.disabled, true);
  assert.equal(b.elements.raceMapping.children.length, 0);
});

test('смена файла до ready не возвращает устаревший полный preview', async () => {
  const b = browser(); await parseFull(b);
  await b.elements.raceFile.emit('change'); b.ready();
  assert.equal(b.fullLayer(), undefined);
  assert.equal(b.elements.confirmRace.disabled, true);
});

test('поздний ответ для сменённого файла не восстанавливает устаревший preview', async () => {
  const b = browser(); b.ready();
  let resolve;
  b.respond(() => new Promise(done => { resolve = done; }));
  const pending = parseFull(b);
  // Программное событие моделирует смену источника при ещё незавершённом запросе
  for (const fn of b.elements.raceFile.listeners.change) fn();
  resolve({lines}); await pending;
  assert.equal(b.fullLayer(), undefined);
  assert.equal(b.elements.raceMapping.children.length, 0);
  assert.equal(b.elements.confirmRace.disabled, true);
});
