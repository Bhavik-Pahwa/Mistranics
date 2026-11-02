/* Rendering and controls only. All motor/sensor calculations run on the server. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  document.querySelector('h1').textContent = 'ESP32 / MPU6050 server motor simulator';
  document.querySelector('.sub').textContent = 'Server-generated simulated sensors. Closing this page does not stop the motor or MQTT publisher.';
  const panel = document.createElement('section');
  panel.className = 'card';
  panel.style.marginBottom = '12px';
  panel.setAttribute('aria-label', 'Simulation server connection');
  panel.innerHTML = '<button id="publish" disabled>Start INDUX publisher</button> <a href="/docs" target="_blank" rel="noreferrer">OpenAPI documentation</a><p id="connection" role="status">Connecting to simulation server…</p><p id="publish-status"></p><p id="control-error" role="alert"></p><p class="desc">All six modes, temperature, waveforms and serial output come from the server. Only temperature enters the INDUX MQTT pipeline. The original demo WARNING/FAULT thresholds below are illustrative; the dashboard calculates its own statistical anomalies.</p>';
  document.body.insertBefore(panel, document.querySelector('.kpis'));
  let state = null, connected = false, busy = false, revision = -1;
  let socket = null, receivedAt = 0, retry = null;
  function enabled() {
    for (const element of document.querySelectorAll('button, input[type="range"]')) element.disabled = !connected || busy;
  }
  function points(values, low, high) {
    return values.map((value, index) => `${(index * 400 / Math.max(values.length - 1, 1)).toFixed(1)},${(150 - (Math.max(low, Math.min(high, value)) - low) / (high - low) * 150).toFixed(1)}`).join(' ');
  }
  function render(next) {
    if (next.revision < revision) return;
    state = next;
    revision = next.revision;
    if (!$('modes').children.length) {
      for (const [mode, [label]] of Object.entries(next.modes)) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = label;
        button.dataset.mode = mode;
        button.onclick = () => control({ mode });
        $('modes').append(button);
      }
    }
    for (const button of $('modes').children) {
      button.classList.toggle('on', button.dataset.mode === next.mode);
      button.setAttribute('aria-pressed', String(button.dataset.mode === next.mode));
    }
    $('desc').textContent = next.modes[next.mode][1];
    $('tmp').textContent = next.temperature.toFixed(1) + ' °C';
    $('rms').textContent = next.rms.toFixed(2) + ' g';
    $('spd').textContent = next.rpm + ' RPM';
    $('state').textContent = next.demo_status;
    const color = { NORMAL: '#22c55e', WARNING: '#f59e0b', FAULT: '#ef4444' }[next.demo_status];
    $('state').style.color = color;
    $('led').setAttribute('fill', color);
    if (document.activeElement !== $('rpm')) $('rpm').value = next.rpm;
    if (document.activeElement !== $('sev')) $('sev').value = next.severity;
    $('rv').textContent = next.rpm + ' RPM';
    $('sv').textContent = next.severity + '%';
    $('pause').textContent = next.paused ? 'Resume' : 'Pause';
    $('publish').textContent = next.publisher_enabled ? 'Stop INDUX publisher' : 'Start INDUX publisher';
    for (const key of ['ax', 'ay', 'az', 'gx', 'gy', 'gz']) {
      $('p' + key).setAttribute('points', points(next.waveforms[key], key.startsWith('a') ? -3 : -100, key.startsWith('a') ? 4 : 100));
    }
    $('pt').setAttribute('points', points(next.temperature_history.length > 1 ? next.temperature_history : [next.temperature, next.temperature], 20, 100));
    $('rot').setAttribute('transform', `rotate(${next.rotation_degrees} 390 143)`);
    const shake = Math.min(8, next.rms * 12);
    const phase = next.rotation_degrees * Math.PI / 180;
    $('cas').setAttribute('transform', `translate(${Math.sin(phase) * shake},${Math.cos(phase) * shake})`);
    const heat = Math.max(0, Math.min(1, (next.temperature - 30) / 50));
    $('body').setAttribute('fill', `rgb(${Math.round(71 + heat * 170)},${Math.round(85 - heat * 40)},${Math.round(105 - heat * 70)})`);
    const serial = next.serial.join('\n');
    if ($('term').textContent !== serial) { $('term').textContent = serial; $('term').scrollTop = $('term').scrollHeight; }
    $('connection').textContent = `Server connected · ${next.paused ? 'Paused' : 'Running'} · ${new Date(next.timestamp).toLocaleTimeString()}`;
    const publishing = !next.publisher_enabled ? 'Publisher stopped' : next.paused ? 'Publishing paused' : 'Publisher running';
    $('publish-status').textContent = `MQTT: ${next.mqtt_connected ? 'Connected' : 'Disconnected'} · ${publishing} · ${next.published_windows} acknowledged windows · ${next.dropped_windows} dropped` + (next.error ? ` · ${next.error}` : '');
    enabled();
  }
  async function control(changes, path = '/api/simulation', method = 'PATCH') {
    if (busy || !connected) return;
    busy = true;
    enabled();
    $('control-error').textContent = '';
    try {
      const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json' },
        body: method === 'PATCH' ? JSON.stringify(changes) : undefined, signal: AbortSignal.timeout(8000) });
      if (!response.ok) throw new Error(`Control rejected (${response.status})`);
      render(await response.json());
    } catch (error) { $('control-error').textContent = error.message; }
    finally { busy = false; enabled(); }
  }
  $('rpm').setAttribute('aria-label', 'Motor speed');
  $('sev').setAttribute('aria-label', 'Anomaly severity');
  $('rpm').onchange = (event) => control({ rpm: Number(event.target.value) });
  $('sev').onchange = (event) => control({ severity: Number(event.target.value) });
  $('rst').onclick = () => control({}, '/api/simulation/cool-down', 'POST');
  $('pause').onclick = () => control({ paused: !state.paused });
  $('publish').onclick = () => control({ publisher_enabled: !state.publisher_enabled });
  function connect() {
    const url = new URL('/ws/simulation', location.href);
    url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const current = new WebSocket(url);
    socket = current;
    receivedAt = Date.now();
    current.onmessage = (event) => {
      if (socket !== current) return;
      try {
        const next = JSON.parse(event.data);
        if (next.type !== 'simulation_state') throw new Error('Unexpected simulation response');
        if (!connected) revision = -1; // Accept reset state after a backend restart.
        connected = true;
        receivedAt = Date.now();
        render(next);
      } catch { current.close(); }
    };
    current.onerror = () => current.close();
    current.onclose = () => {
      if (socket !== current) return;
      connected = false;
      enabled();
      $('connection').textContent = 'Server disconnected · last displayed values are stale · reconnecting';
      $('publish-status').textContent = 'MQTT status unknown while disconnected';
      retry = setTimeout(connect, 1000);
    };
  }
  setInterval(() => { if (Date.now() - receivedAt > 3000 && socket?.readyState < 2) socket.close(); }, 500);
  window.addEventListener('pagehide', () => { clearTimeout(retry); const current = socket; socket = null; current?.close(); });
  enabled();
  connect();
})();
