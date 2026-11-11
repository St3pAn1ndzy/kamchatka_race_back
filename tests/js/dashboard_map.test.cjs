// Проверки обновления карты без сброса выбранного пользователем масштаба
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function harness(responses) {
  const intervals = [];
  const maps = [];
  const nodes = new Map();
  const placemarks = [];
  class Collection {
    constructor() { this.items = []; }
    add(item) { this.items.push(item); }
    removeAll() { this.items = []; }
    remove(item) { this.items = this.items.filter(value => value !== item); }
  }
  class Shape {
    constructor(coords, properties = {}, options = {}) {
      this.coords = coords;
      this.props = properties;
      this.opts = options;
      this.geometry = {setCoordinates: value => {this.coords = value;}};
      this.properties = {set: values => Object.assign(this.props, values)};
      this.options = {set: values => Object.assign(this.opts, values)};
    }
  }
  class Placemark extends Shape {
    constructor(...args) { super(...args); placemarks.push(this); }
  }
  class MapView {
    constructor() {
      this.geoObjects = new Collection();
      this.bounds = [];
      this.centers = [];
      this.container = {fitToViewport() {}};
      maps.push(this);
    }
    setBounds(value) { this.bounds.push(value); }
    setCenter(value) { this.centers.push(value); }
  }
  const context = {
    window: {},
    console: {error() {}},
    document: {
      getElementById(id) {
        if (!nodes.has(id)) nodes.set(id, {style: {}, textContent: '', scrollIntoView() {}});
        return nodes.get(id);
      },
      querySelectorAll() {return [];},
    },
    ymaps: {ready: callback => callback(), Map: MapView, Polyline: Shape,
      Placemark, GeoObjectCollection: Collection, Clusterer: Collection},
    setInterval: callback => {intervals.push(callback);},
    fetch: async () => {
      const next = responses.shift();
      if (next instanceof Error) throw next;
      return {ok: true, redirected: false, json: async () => next};
    },
    Date,
    Number,
    Map,
  };
  vm.runInNewContext(fs.readFileSync('app/static/js/dashboard_map.js', 'utf8'), context);
  return {maps, placemarks, nodes, intervals, window: context.window};
}
const flush = () => new Promise(resolve => setImmediate(resolve));
function data(lat = 53) {
  return {route: [{lat: 53, lon: 158}, {lat: 54, lon: 159}], checkpoints: [],
    participants: [{device_id: 1, participant_id: 7, number: 7, name: '<Каюр>', lat, lon: 158.2, sos: false}]};
}

test('Опрос двигает существующий маркер, не сбрасывая масштаб или положение карты', async () => {
  const second = data(53.1); second.participants[0].sos = true;
  const h = harness([data(), second]); await flush();
  const marker = h.placemarks[0];
  const layers = [...h.maps[0].geoObjects.items];
  assert.equal(h.maps[0].bounds.length, 1);
  await h.intervals[0](); await flush();
  assert.equal(h.placemarks.length, 1);
  assert.equal(h.placemarks[0], marker);
  assert.equal(marker.coords[0], 53.1);
  assert.equal(marker.opts.preset, 'islands#redDotIcon');
  assert.equal(h.maps[0].bounds.length, 1);
  assert.equal(h.maps[0].centers.length, 0);
  assert.deepEqual(h.maps[0].geoObjects.items, layers);
  assert.ok(marker.props.balloonContent.includes('&lt;Каюр&gt;'));
  h.window.resetMapView();
  assert.equal(h.maps[0].bounds.length, 2);
});

test('Нулевые координаты отображаются, исчезнувшие устройства удаляются из слоя', async () => {
  const first = data(0); first.participants[0].lon = 0;
  const empty = data(); empty.participants = [];
  const h = harness([first, empty]); await flush();
  assert.equal(h.placemarks.length, 1);
  const cluster = h.maps[0].geoObjects.items.find(layer => layer.items);
  assert.equal(cluster.items.length, 1);
  await h.intervals[0](); await flush();
  assert.equal(cluster.items.length, 0);
});

test('Ошибка запроса сохраняет прежние маркеры и выбранный масштаб', async () => {
  const h = harness([data(), new Error('Нет связи')]); await flush();
  const marker = h.placemarks[0];
  await h.intervals[0](); await flush();
  assert.equal(h.placemarks[0], marker);
  assert.equal(h.maps[0].bounds.length, 1);
  assert.equal(h.nodes.get('map-updated').textContent, 'Ошибка обновления');
});
