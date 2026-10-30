// Проверки последовательного опроса и сохранения тревоги при ошибках связи
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}

function response(sos) {
  return {ok: true, redirected: false, json: async () => ({sos})};
}

const alarm = [{participant_number: 7, participant_name: 'Каюр',
  device_name: 'Трекер', last_message_at: null}];
const flush = () => new Promise(resolve => setImmediate(resolve));

function harness(responses) {
  const intervals = [];
  const requests = [];
  const container = {children: [], replaceChildren(...children) { this.children = children; }};
  const context = {
    document: {
      getElementById: id => id === 'dashboard-sos' ? container : null,
      createElement: () => ({children: [], append(child) { this.children.push(child); }}),
    },
    fetch: (url, options) => {
      requests.push({url, options});
      assert.ok(responses.length, 'Неожиданный запрос опроса');
      return responses.shift();
    },
    setInterval: callback => { intervals.push(callback); },
  };
  vm.runInNewContext(fs.readFileSync(
    path.join(__dirname, '../../app/static/js/dashboard_sos.js'), 'utf8'), context);
  return {container, requests, poll: () => intervals[0]()};
}

test('Ожидающий ответ опрос не запускает параллельный запрос', async () => {
  const pending = deferred();
  const h = harness([response(alarm), pending.promise, response(alarm)]);
  await flush();
  const card = h.container.children[0];
  assert.ok(card);

  const polling = h.poll();
  await h.poll();
  assert.equal(h.requests.length, 2);
  assert.equal(h.container.children[0], card);

  pending.resolve(response([]));
  await polling;
  assert.equal(h.container.children.length, 0);
  await h.poll();
  assert.equal(h.requests.length, 3);
  assert.equal(h.container.children.length, 1);
});

test('Ожидание JSON удерживает опрос занятым до обновления тревоги', async () => {
  const body = deferred();
  const h = harness([response(alarm),
    {ok: true, redirected: false, json: () => body.promise}, response(alarm)]);
  await flush();
  const card = h.container.children[0];
  assert.ok(card);

  const polling = h.poll();
  await flush();
  await h.poll();
  assert.equal(h.requests.length, 2);
  assert.equal(h.container.children[0], card);

  body.resolve({sos: []});
  await polling;
  assert.equal(h.container.children.length, 0);
  await h.poll();
  assert.equal(h.requests.length, 3);
  assert.equal(h.container.children.length, 1);
});

test('Ошибка запроса сохраняет тревогу и разрешает повторный опрос', async () => {
  const pending = deferred();
  const h = harness([response(alarm), pending.promise, response([])]);
  await flush();
  const card = h.container.children[0];
  assert.ok(card);

  const polling = h.poll();
  pending.reject(new Error('Нет связи'));
  await polling;
  assert.equal(h.container.children[0], card);

  await h.poll();
  assert.equal(h.requests.length, 3);
  assert.equal(h.container.children.length, 0);
});
