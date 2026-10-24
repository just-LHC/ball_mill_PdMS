import React, { useEffect, useRef, useState } from 'react';
import { getWebSocketBaseUrl } from '../api';

function formatSampleTime(value) {
  if (!value) return 'No demo sample received';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Sample time unavailable' : date.toLocaleString();
}

function getTrendPoints(samples) {
  const values = samples.map((sample) => sample.vib).filter(Number.isFinite);
  if (!values.length) return { points: '', low: null, middle: null, high: null };
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const padding = Math.max((maximum - minimum) * 0.15, Math.abs(maximum) * 0.05, 0.1);
  const low = minimum - padding;
  const high = maximum + padding;
  const points = samples.flatMap((sample, index) => {
    if (!Number.isFinite(sample.vib)) return [];
    const x = values.length < 2 ? 220 : 50 + index / Math.max(samples.length - 1, 1) * 340;
    const y = 105 - ((sample.vib - low) / (high - low)) * 80;
    return [`${x},${y}`];
  }).join(' ');
  return { points, low, middle: (low + high) / 2, high };
}

export default function EquipmentChart({ mill = "Mill 6", equipment = "Mill Main Control", backendUrl }) {
  const [telemetry, setTelemetry] = useState([]);
  const [status, setStatus] = useState('Connecting to demo feed');
  const lastReceivedAt = useRef(null);

  useEffect(() => {
    const wsUrl = `${getWebSocketBaseUrl(backendUrl)}/ws/telemetry/${encodeURIComponent(mill)}/${encodeURIComponent(equipment)}`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => setStatus('Connected · DEMO DATA');
    ws.onerror = () => setStatus('Demo feed connection error');
    ws.onclose = () => setStatus('Demo feed disconnected');

    ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        setStatus('Invalid demo feed message');
        return;
      }
      const sensors = Array.isArray(data.sensors) ? data.sensors : [];
      const time = data.sample_time || new Date().toISOString();
      lastReceivedAt.current = Date.now();

      setTelemetry((prev) => [
        ...prev.slice(-19),
        {
          time,
          vib: sensors.find((sensor) => sensor.kind === 'vibration')?.value ?? null,
          temp: sensors.find((sensor) => sensor.kind === 'temperature')?.value ?? null,
        }
      ]);
      setStatus('Connected · DEMO DATA');
    };

    const staleTimer = window.setInterval(() => {
      if (lastReceivedAt.current && Date.now() - lastReceivedAt.current > 5000) setStatus('STALE DEMO DATA');
    }, 1000);
    return () => {
      window.clearInterval(staleTimer);
      ws.close();
    };
  }, [mill, equipment, backendUrl]);

  const latest = telemetry[telemetry.length - 1] || { vib: null, temp: null };
  const { points, low, middle, high } = getTrendPoints(telemetry);
  const formatTime = (value) => value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';
  const connectionState = status.includes('STALE') ? 'telemetry-stale' : status.includes('error') || status.includes('disconnected') ? 'telemetry-error' : 'telemetry-connected';

  return (
    <section className="equipment-panel">
      <div className="equipment-heading">
        <div>
          <p className="equipment-kicker">DEMO TELEMETRY <span>·</span> SENSOR TAGS NOT CONFIGURED</p>
          <h2>{mill} <span className="heading-separator">/</span> {equipment}</h2>
        </div>
        <div className={`connection-status ${connectionState}`}><span className={`status-dot ${connectionState}`} />{status} · NO PLC CONNECTION</div>
      </div>

      <div className="telemetry-grid">
        <div className="metric">
          <div className="metric-label">VIBRATION RMS <span>mm/s</span></div>
          <p className="metric-value">{latest.vib !== null && Number.isFinite(Number(latest.vib)) ? Number(latest.vib).toFixed(1) : '—'}<span className="metric-unit">mm/s</span></p>
          <p className="metric-note">Demo sample · tag not configured</p>
        </div>
        <div className="metric">
          <div className="metric-label">BEARING TEMP <span>°C</span></div>
          <p className="metric-value">{latest.temp !== null && Number.isFinite(Number(latest.temp)) ? Number(latest.temp).toFixed(1) : '—'}<span className="metric-unit">°C</span></p>
          <p className="metric-note">Demo sample · tag not configured</p>
        </div>
      </div>

      <div className="chart-heading"><span>Vibration · DEMO DATA</span><span>{telemetry.length} RECEIVED SAMPLES · MAX 20</span></div>
      <svg className="telemetry-chart" viewBox="0 0 400 126" role="img" aria-label={`Demo vibration samples for ${equipment}, latest sample ${formatSampleTime(latest.time)}`} preserveAspectRatio="none">
        <line x1="48" y1="25" x2="394" y2="25" className="chart-gridline" />
        <line x1="48" y1="65" x2="394" y2="65" className="chart-gridline" />
        <line x1="48" y1="105" x2="394" y2="105" className="chart-gridline" />
        <text className="chart-axis-label" x="0" y="14">mm/s</text>
        <text className="chart-axis-label" x="0" y="28">{high === null ? '—' : high.toFixed(1)}</text>
        <text className="chart-axis-label" x="0" y="68">{middle === null ? '—' : middle.toFixed(1)}</text>
        <text className="chart-axis-label" x="0" y="108">{low === null ? '—' : low.toFixed(1)}</text>
        <polyline fill="none" className="chart-line" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" points={points} />
      </svg>
      <div className="chart-axis"><span title={formatSampleTime(telemetry[0]?.time)}>{formatTime(telemetry[0]?.time)}</span><span title={formatSampleTime(latest.time)}>{formatTime(latest.time)}</span></div>
    </section>
  );
}
