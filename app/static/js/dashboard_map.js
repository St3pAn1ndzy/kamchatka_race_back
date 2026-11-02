// Обновляет данные карты, сохраняя выбранный пользователем масштаб и положение
(function () {
  const updated = document.getElementById('map-updated');
  const loader = document.getElementById('mapLoader');
  if (typeof ymaps === 'undefined') {
    if (updated) updated.textContent = 'API Карт не загружено';
    return;
  }
  function escaped(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return {'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char];
    });
  }
  function hasPosition(item) {
    return Number.isFinite(item.lat) && Number.isFinite(item.lon);
  }
  ymaps.ready(function () {
    const map = new ymaps.Map('miniMap', {
      center: [53.0, 158.7], zoom: 8, controls: ['zoomControl', 'fullscreenControl']
    });
    map.container.fitToViewport();
    const cluster = new ymaps.Clusterer({
      preset: 'islands#invertedVioletClusterIcons', groupByCoordinates: false,
      clusterDisableClickZoom: false, clusterHideIconOnBalloonOpen: false,
      geoObjectHideIconOnBalloonOpen: false
    });
    map.geoObjects.add(cluster);
    const markers = new Map();
    let route = null, checkpoints = null, geometryKey = null, allCoords = [];
    let fitted = false, busy = false;

    function fitAll() {
      if (!allCoords.length) return;
      let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
      allCoords.forEach(function (coord) {
        minLat = Math.min(minLat, coord[0]); maxLat = Math.max(maxLat, coord[0]);
        minLon = Math.min(minLon, coord[1]); maxLon = Math.max(maxLon, coord[1]);
      });
      map.setBounds([[minLat, minLon], [maxLat, maxLon]], {checkZoomRange: true, zoomMargin: 80});
      fitted = true;
    }
    window.resetMapView = fitAll;

    function updateGeometry(data) {
      const key = JSON.stringify([data.route || [], data.checkpoints || []]);
      if (key === geometryKey) return;
      if (route) map.geoObjects.remove(route);
      if (checkpoints) map.geoObjects.remove(checkpoints);
      route = null;
      const coords = (data.route || []).filter(hasPosition).map(p => [p.lat, p.lon]);
      if (coords.length) {
        route = new ymaps.Polyline(coords, {}, {strokeColor: '#005A9C', strokeWidth: 4, strokeOpacity: 0.8});
        map.geoObjects.add(route);
      }
      checkpoints = new ymaps.GeoObjectCollection();
      (data.checkpoints || []).filter(hasPosition).forEach(function (cp) {
        const color = cp.kind === 'start' ? '#2fb344' : cp.kind === 'finish' ? '#d63939' : '#f59f00';
        checkpoints.add(new ymaps.Placemark([cp.lat, cp.lon], {
          hintContent: escaped(cp.code) + ' — ' + escaped(cp.name),
          balloonContent: '<b>' + escaped(cp.code) + '</b><br>' + escaped(cp.name)
        }, {preset: 'islands#circleDotIcon', iconColor: color}));
      });
      map.geoObjects.add(checkpoints);
      geometryKey = key;
    }

    function updateParticipants(participants) {
      const seen = new Set();
      participants.filter(hasPosition).forEach(function (p) {
        const key = p.device_id != null ? 'device:' + p.device_id : 'participant:' + (p.participant_id ?? p.number);
        seen.add(key);
        const coords = [p.lat, p.lon];
        const properties = {
          hintContent: '№' + escaped(p.number ?? '?') + ' ' + escaped(p.name),
          balloonContent: '<div class="p-1"><b>Участник №' + escaped(p.number ?? '?') + '</b><br>' + escaped(p.name) + '</div>'
        };
        const preset = p.sos ? 'islands#redDotIcon' : 'islands#blueDotIcon';
        let entry = markers.get(key);
        if (!entry) {
          entry = {marker: new ymaps.Placemark(coords, properties, {preset}), coords};
          markers.set(key, entry);
          cluster.add(entry.marker);
        } else {
          // Кластер пересчитывает положение, но объект маркера остаётся прежним
          if (entry.coords[0] !== coords[0] || entry.coords[1] !== coords[1]) {
            cluster.remove(entry.marker);
            entry.marker.geometry.setCoordinates(coords);
            cluster.add(entry.marker);
            entry.coords = coords;
          }
          entry.marker.properties.set(properties);
          entry.marker.options.set({preset});
        }
      });
      markers.forEach(function (entry, key) {
        if (!seen.has(key)) {cluster.remove(entry.marker); markers.delete(key);}
      });
    }

    async function refresh() {
      if (busy) return;
      busy = true;
      try {
        const response = await fetch('/admin-panel/api/dashboard-map-data', {cache: 'no-store'});
        if (!response.ok || response.redirected) throw new Error('Ошибка получения карты');
        const data = await response.json();
        if (!Array.isArray(data.participants) || !Array.isArray(data.route) || !Array.isArray(data.checkpoints)) {
          throw new Error('Некорректные данные карты');
        }
        updateGeometry(data);
        updateParticipants(data.participants);
        allCoords = [...data.route, ...data.checkpoints, ...data.participants].filter(hasPosition).map(p => [p.lat, p.lon]);
        if (!fitted) fitAll();
        if (loader) loader.style.display = 'none';
        if (updated) updated.textContent = 'Обновлено ' + new Date().toLocaleTimeString('ru-RU', {hour:'2-digit', minute:'2-digit', second:'2-digit'});
      } catch (error) {
        if (updated) updated.textContent = 'Ошибка обновления';
        if (!fitted && loader) loader.textContent = 'Не удалось загрузить карту';
      } finally {busy = false;}
    }
    document.querySelectorAll('.show-on-map').forEach(function (button) {
      button.addEventListener('click', function () {
        const lat = Number.parseFloat(this.getAttribute('data-lat'));
        const lon = Number.parseFloat(this.getAttribute('data-lon'));
        if (Number.isFinite(lat) && Number.isFinite(lon)) {
          map.setCenter([lat, lon], 13, {duration: 300});
          fitted = true;
          document.getElementById('miniMap').scrollIntoView({behavior:'smooth', block:'center'});
        }
      });
    });
    refresh();
    setInterval(refresh, 5000);
  });
})();
