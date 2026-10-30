// Обновляет тревоги независимо от доступности внешнего API карт
(function () {
  const container = document.getElementById('dashboard-sos');
  if (!container) return;

  function render(devices) {
    if (!Array.isArray(devices)) return;
    const card = document.createElement('div');
    card.className = 'card border-danger mb-4 shadow-sm';
    const body = document.createElement('div');
    body.className = 'card-body';
    const title = document.createElement('h2');
    title.className = 'text-danger';
    title.textContent = 'SOS! Сигнал требует проверки';
    body.append(title);
    devices.forEach(function (device) {
      const row = document.createElement('div');
      row.className = 'mb-2';
      // Имена из базы вставляются как текст, без интерпретации HTML
      const date = new Date(device.last_message_at);
      const time = device.last_message_at && !Number.isNaN(date.getTime())
        ? date.toLocaleString('ru-RU') : 'Нет времени';
      row.textContent = '№' + (device.participant_number ?? '—') + ' ' +
        (device.participant_name || 'Участник не назначен') + ' · ' +
        (device.device_name || 'Трекер') + ' · ' + time;
      body.append(row);
    });
    const link = document.createElement('a');
    link.href = '/admin-panel/race-control';
    link.className = 'btn btn-danger btn-sm';
    link.textContent = 'Открыть Штаб';
    body.append(link);
    card.append(body);
    container.replaceChildren(...(devices.length ? [card] : []));
  }

  let busy = false;
  async function refresh() {
    if (busy) return;
    busy = true;
    try {
      const response = await fetch('/admin-panel/api/dashboard-stats', {cache: 'no-store'});
      if (!response.ok || response.redirected) return;
      const data = await response.json();
      render(data.sos);
      const stale = document.getElementById('metric-stale');
      if (stale && data.stats && Number.isInteger(data.stats.devices_stale)) {
        const count = data.stats.devices_stale;
        stale.className = (count ? 'text-danger' : 'text-success') + ' small fw-bold mt-3';
        stale.textContent = count ? count + ' потеряли связь!' : 'Все на связи';
      }
    } catch (_) {
      // Ошибка связи не должна скрывать последнюю известную тревогу
    } finally {
      busy = false;
    }
  }
  refresh();
  setInterval(refresh, 5000);
})();
