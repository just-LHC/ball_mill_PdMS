import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Activity, AlertTriangle, CalendarDays, Check, ChevronLeft, ChevronRight, Download, Factory, Fan, Gauge, RefreshCw, Wrench } from 'lucide-react';
import { getBackendBaseUrl, getWebSocketBaseUrl } from '../api';
import { sanitizeAlertText } from '../alertText';
import mill5Gearbox1Photo from '../../mill_photos/mill_5/m5 gearbox1.jpg';
import mill5Gearbox2Photo from '../../mill_photos/mill_5/gearbox 2.jpg';
import mill5SeparatorFilterFanPhoto from '../../mill_photos/mill_5/Separator Filter Fan.jpg';
import mainMillControlMill1Photo from '../../mill_photos/Mill_1/main milL1.jpg';
import mainMillControlMill4Photo from '../../mill_photos/mill_4/main milL4.jpg';
import mainMillControlPhoto from '../../mill_photos/mill_6/main mill6 control.jpg';
import mainMillControlDetailPhoto from '../../mill_photos/mill_6/main mill6 control_1.jpg';
import slideShoeBearingPhoto from '../../mill_photos/mill_6/Slide Shoe Bearing1.jpg';
import slideShoeBearingDetailPhoto from '../../mill_photos/mill_6/Slide Shoe Bearing 2.jpg';
import separatorFilterFanPhoto from '../../mill_photos/mill_6/ventilateur filtre separateur.jpg';
import mainFilterFanPhoto from '../../mill_photos/mill_6/ventilateur filtre principal.jpg';
import dynamicSeparatorPhoto from '../../mill_photos/mill_6/separateur dynamique.jpg';

const MONITOR_VIEWS = ['Subsystem Overview', 'Equipment Drill-Down', 'Servicing Desk & Alert Log'];
const ALERT_PAGE_SIZE = 10;
const SUBSYSTEM_PHOTOS = {
  'Mill 5': {
    'Mill Main Control': {
      'Gearbox 1': [mill5Gearbox1Photo],
      'Gearbox 2': [mill5Gearbox2Photo],
    },
    'Separator Filter Fan': [mill5SeparatorFilterFanPhoto],
  },
  'Mill 1': {
    'Mill Main Control': [mainMillControlMill1Photo],
  },
  'Mill 4': {
    'Mill Main Control': [mainMillControlMill4Photo],
  },
  'Mill 6': {
    'Mill Main Control': [mainMillControlPhoto, mainMillControlDetailPhoto],
    'Slide Shoe Bearing': [slideShoeBearingPhoto, slideShoeBearingDetailPhoto],
    'Main Filter Fan': [mainFilterFanPhoto],
    'Separator Filter Fan': [separatorFilterFanPhoto],
    'Dynamic Separator': [dynamicSeparatorPhoto],
  },
};

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function telemetryStateClass(status = '') {
  if (status.includes('STALE')) return 'telemetry-stale';
  if (status.includes('ERROR') || status.includes('DISCONNECTED') || status.includes('INVALID')) return 'telemetry-error';
  if (status.includes('CONNECTED')) return 'telemetry-connected';
  return 'telemetry-pending';
}

function formatValue(value, unit) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—';
  return `${Number(value).toFixed(1)} ${unit || ''}`.trim();
}

function severityClass(severity) {
  const normalized = String(severity || '').toUpperCase();
  return normalized === 'CRITICAL' ? 'severity-critical' : normalized === 'WARNING' ? 'severity-warning' : 'severity-neutral';
}

function EquipmentIcon({ equipment, size = 23 }) {
  const normalized = String(equipment || '').toLowerCase();
  if (normalized.includes('fan')) return <Fan size={size} strokeWidth={1.6} />;
  if (normalized.includes('separator')) return <Gauge size={size} strokeWidth={1.6} />;
  if (normalized.includes('pump')) return <Activity size={size} strokeWidth={1.6} />;
  return <Factory size={size} strokeWidth={1.6} />;
}

function getSamples(reading, sensor) {
  const samples = reading?.samples || [];
  const values = samples.map((sample) => Number(sample.values?.[sensor.channel_key])).filter(Number.isFinite);
  if (!values.length) return { points: '', low: null, middle: null, high: null };
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const padding = Math.max((maximum - minimum) * 0.15, Math.abs(maximum) * 0.03, 0.1);
  const low = minimum - padding;
  const high = maximum + padding;
  const range = high - low;
  const points = values.map((value, index) => {
    const x = values.length < 2 ? 220 : 52 + index / (values.length - 1) * 340;
    const y = 108 - ((value - low) / range) * 84;
    return `${x},${y}`;
  }).join(' ');
  return { points, low, middle: (low + high) / 2, high };
}

function SensorChart({ sensor, reading }) {
  const latest = reading?.sensors?.find((item) => item.channel_key === sensor.channel_key);
  const { points, low, middle, high } = getSamples(reading, sensor);
  const samples = reading?.samples || [];
  const firstSample = samples[0]?.sample_time;
  const lastSample = samples.at(-1)?.sample_time;
  const formatTick = (value) => value === null ? '—' : Number(value).toFixed(1);
  const formatTime = (value) => value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';

  return (
    <article className="sensor-chart-panel">
      <div className="sensor-chart-header">
        <div><p>{sensor.name}</p><span>{sensor.tag || 'TAG NOT CONFIGURED'} <i>/</i> {sensor.unit}</span></div>
        <strong className="sensor-chart-value">{formatValue(latest?.value, sensor.unit)}</strong>
      </div>
      <svg viewBox="0 0 400 132" className="sensor-chart" role="img" aria-label={`${sensor.name} demo samples, ${samples.length} points from ${formatTime(firstSample)} to ${formatTime(lastSample)}`} preserveAspectRatio="none">
        <line x1="50" y1="24" x2="394" y2="24" />
        <line x1="50" y1="66" x2="394" y2="66" />
        <line x1="50" y1="108" x2="394" y2="108" />
        <text x="1" y="12">{sensor.unit}</text>
        <text x="0" y="27">{formatTick(high)}</text>
        <text x="0" y="69">{formatTick(middle)}</text>
        <text x="0" y="111">{formatTick(low)}</text>
        <polyline points={points} />
      </svg>
      <div className="sensor-chart-axis"><span>{formatTime(firstSample)}</span><span>{formatTime(lastSample)}</span></div>
      <div className="sensor-chart-window">DEMO DATA · {samples.length} RECEIVED SAMPLES · UP TO 60 IN THIS SESSION</div>
    </article>
  );
}

function SensorSummary({ equipment, configuredSensors, reading }) {
  const sensors = reading?.sensors?.length ? reading.sensors : configuredSensors;
  return (
    <article className="subsystem-summary-row">
      <div className="subsystem-summary-name"><span className="subsystem-icon"><EquipmentIcon equipment={equipment} /></span><div><strong>{equipment}</strong><span className={`telemetry-state ${telemetryStateClass(reading?.status)}`} role="status" aria-live="polite">{reading?.status || 'WAITING FOR DEMO DATA'}{reading?.sampleTime ? ` · Sample ${formatDate(reading.sampleTime)}` : ''}</span></div></div>
      {sensors.length ? (
        <div className="subsystem-sensor-values">
          {sensors.map((sensor) => <div className="subsystem-sensor-value" key={sensor.channel_key}><span>{sensor.name}</span><strong>{formatValue(sensor.value, sensor.unit)}</strong><small>{sensor.tag || 'TAG NOT CONFIGURED'} · {sensor.source || `DEMO DATA · ${sensor.source_label ? `${sensor.source_label} label` : 'source label not configured'}`}</small></div>)}
        </div>
      ) : <div className="no-live-values">No sensor inventory is configured.</div>}
    </article>
  );
}

function SubsystemOverview({ mill, displayName, inventoryStatus, equipmentList, equipmentConfig, readings, onSelectSubsystem }) {
  return (
    <section className="monitor-view-content">
      <div className="monitor-section-heading"><div><p className="section-index">01 <span>/</span> DEMO CONDITION</p><h2>{displayName || mill} subsystem overview</h2></div><span className="demo-stream-label"><span /> DEMO DATA · NO PLC CONNECTION</span></div>
      <div className="live-banner"><Activity size={16} /><span>Simulated demo samples update every second</span><span className="live-banner-note">No PLC or plant historian is connected. Values are not operational measurements.</span></div>
      <div className="subsystem-list">
        {equipmentList.length ? equipmentList.map((equipment) => (
          <div className="subsystem-summary-item" key={equipment}>
            <SensorSummary equipment={equipment} configuredSensors={equipmentConfig[equipment] || []} reading={readings[equipment]} />
            <button type="button" className="subsystem-open-button" onClick={() => onSelectSubsystem(equipment)}>DETAILS</button>
          </div>
        )) : <div className="monitor-empty">{inventoryStatus === 'NOT_CONFIGURED' ? `${mill} equipment inventory is not configured. Equipment is not inferred from alert history.` : `No equipment has been configured for ${mill}.`}</div>}
      </div>
      <div className="sensor-tag-note">Sensor tags are not configured. Descriptive channel names are for demo display only; confirm the plant tag register before operational use.</div>
    </section>
  );
}

function SensorRegister({ title, sensors }) {
  return (
    <div className="sensor-register-panel">
      <div className="sensor-register-heading"><span>{title}</span><span>{sensors.length} CHANNELS</span></div>
      {sensors.map((sensor) => (
        <div className="sensor-register-row" key={sensor.channel_key}>
          <span className="sensor-register-led" />
          <div><strong>{sensor.name}</strong><small>{sensor.tag || 'TAG NOT CONFIGURED'} · {sensor.source || `DEMO DATA · ${sensor.source_label ? `${sensor.source_label} label` : 'source label not configured'}`}</small></div>
          <b>{sensor.unit}</b>
        </div>
      ))}
    </div>
  );
}

function EquipmentDrillDown({ mill, displayName, inventoryStatus, equipmentList, equipmentConfig, selectedEquipment, onEquipmentChange, reading }) {
  const sensors = reading?.sensors?.length ? reading.sensors : equipmentConfig[selectedEquipment] || [];
  const componentOptions = [...new Set(sensors.map((sensor) => sensor.component).filter(Boolean))];
  const [selectedComponent, setSelectedComponent] = useState('');
  const activeComponent = componentOptions.includes(selectedComponent) ? selectedComponent : componentOptions[0] || '';
  const displayedSensors = activeComponent ? sensors.filter((sensor) => sensor.component === activeComponent) : sensors;
  const balanceMill5Gearbox = mill === 'Mill 5' && selectedEquipment === 'Mill Main Control' && activeComponent.startsWith('Gearbox ');
  const balanceGearboxOne = balanceMill5Gearbox && activeComponent === 'Gearbox 1';
  const balanceGearboxTwo = balanceMill5Gearbox && activeComponent === 'Gearbox 2';
  const balanceMill6MainControl = mill === 'Mill 6' && selectedEquipment === 'Mill Main Control';
  const balanceSlideShoeBearing = mill === 'Mill 6' && selectedEquipment === 'Slide Shoe Bearing';
  const balanceTemperaturesUnderPhoto = balanceMill5Gearbox || balanceMill6MainControl;
  const slideShoeSplitIndex = Math.ceil(displayedSensors.length / 2);
  const photoSideSensors = balanceTemperaturesUnderPhoto
    ? displayedSensors.filter((sensor) => sensor.kind === 'temperature')
    : balanceSlideShoeBearing ? displayedSensors.slice(0, slideShoeSplitIndex) : [];
  const infoSideSensors = balanceTemperaturesUnderPhoto
    ? displayedSensors.filter((sensor) => sensor.kind !== 'temperature')
    : balanceSlideShoeBearing ? displayedSensors.slice(slideShoeSplitIndex) : displayedSensors;
  const photoSensorTitle = balanceSlideShoeBearing
    ? 'TEMPERATURE CHANNELS · DISPLAY GROUP 1'
    : balanceMill6MainControl ? 'MOTOR & GEARBOX TEMPERATURES' : balanceGearboxTwo ? 'GEARBOX 2 & MOTOR TEMPERATURES' : `${activeComponent} TEMPERATURES`;
  const infoSensorTitle = balanceSlideShoeBearing
    ? 'TEMPERATURE CHANNELS · DISPLAY GROUP 2'
    : balanceMill6MainControl ? 'MOTOR & GEARBOX VIBRATIONS' : balanceGearboxOne ? `${activeComponent} VIBRATION & MOTOR CHANNELS` : balanceGearboxTwo ? 'GEARBOX 2 VIBRATION CHANNELS' : 'AVAILABLE SENSOR CHANNELS';
  const prediction = reading?.prediction;
  const photoEntry = SUBSYSTEM_PHOTOS[mill]?.[selectedEquipment];
  const photos = Array.isArray(photoEntry) ? photoEntry : photoEntry?.[activeComponent] || [];
  const [photoIndex, setPhotoIndex] = useState(0);

  useEffect(() => {
    setSelectedComponent('');
    setPhotoIndex(0);
  }, [mill, selectedEquipment]);
  useEffect(() => setPhotoIndex(0), [activeComponent]);

  if (!equipmentList.length) {
    return <section className="monitor-view-content"><div className="monitor-section-heading"><div><p className="section-index">02 <span>/</span> ASSET DETAIL</p><h2>Equipment drill-down</h2></div></div><div className="monitor-empty">{inventoryStatus === 'NOT_CONFIGURED' ? `${mill} equipment inventory is not configured. Equipment is not inferred from alert history.` : `No equipment has been configured for ${mill}.`}</div></section>;
  }
  return (
    <section className="monitor-view-content">
      <div className="monitor-section-heading"><div><p className="section-index">02 <span>/</span> ASSET DETAIL</p><h2>Equipment drill-down</h2></div><span className="demo-stream-label"><span /> DEMO DATA ONLY</span></div>
      <div className="drilldown-select-row">
        <label htmlFor="subsystem-select">SELECT SUBSYSTEM</label>
        <select id="subsystem-select" value={selectedEquipment} onChange={(event) => onEquipmentChange(event.target.value)}>
          {equipmentList.map((equipment) => <option value={equipment} key={equipment}>{equipment}</option>)}
        </select>
        {componentOptions.length > 1 && <>
          <label htmlFor="equipment-component-select">SELECT COMPONENT</label>
          <select id="equipment-component-select" value={activeComponent} onChange={(event) => setSelectedComponent(event.target.value)}>
            {componentOptions.map((component) => <option value={component} key={component}>{component}</option>)}
          </select>
        </>}
        <span>{displayName || mill}</span>
      </div>
      <div className="demo-sample-context" role="status" aria-live="polite">
        <strong className={`telemetry-state ${telemetryStateClass(reading?.status)}`}>{reading?.status || 'WAITING FOR DEMO DATA'}</strong>
        <span>Sample time: {formatDate(reading?.sampleTime)}</span>
        <span>Demo data only · no PLC connection</span>
      </div>
      <div className="subsystem-detail-layout">
        <div className="subsystem-visual-column">
          {photos.length ? (
            <figure className="subsystem-image-frame subsystem-photo-frame">
              <img className="subsystem-photo" src={photos[photoIndex]} alt={`${mill} ${selectedEquipment} ${activeComponent || ''} reference photo ${photoIndex + 1}`} />
              {photos.length > 1 && <figcaption className="subsystem-photo-controls">
                <span>PHOTO {photoIndex + 1} OF {photos.length}</span>
                <div>
                  <button type="button" aria-label="Previous subsystem photo" title="Previous photo" onClick={() => setPhotoIndex((index) => (index - 1 + photos.length) % photos.length)}><ChevronLeft size={16} /></button>
                  <button type="button" aria-label="Next subsystem photo" title="Next photo" onClick={() => setPhotoIndex((index) => (index + 1) % photos.length)}><ChevronRight size={16} /></button>
                </div>
              </figcaption>}
            </figure>
          ) : (
            <div className="subsystem-image-frame" role="img" aria-label={`Reference photo not configured for ${selectedEquipment}${activeComponent ? ` ${activeComponent}` : ''}`}>
              <div className="schematic-grid" />
              <div className="schematic-machine"><EquipmentIcon equipment={selectedEquipment} size={58} /><span className="schematic-axis" /><span className="schematic-sensor-dot sensor-one" /><span className="schematic-sensor-dot sensor-two" /></div>
              <div className="schematic-label">{activeComponent || selectedEquipment}</div>
              <div className="image-unavailable-label">{activeComponent ? `${activeComponent.toUpperCase()} PHOTO NOT CONFIGURED` : 'PHOTO NOT CONFIGURED'}</div>
            </div>
          )}
          {photoSideSensors.length > 0 && <SensorRegister title={photoSensorTitle} sensors={photoSideSensors} />}
        </div>
        <div className="subsystem-info">
          <p className="equipment-kicker">SELECTED SUBSYSTEM</p>
          <h3>{selectedEquipment || 'Choose a subsystem'}{activeComponent ? ` / ${activeComponent}` : ''}</h3>
            <p className="subsystem-description">Demo sensor channels for {mill}. No live PLC data or verified model configuration is available.</p>
            {prediction && <div className="subsystem-prediction"><span>MODEL STATUS</span><strong className="severity-neutral">{prediction.available ? prediction.score_label : 'NOT CONFIGURED'}</strong><p>{prediction.diagnostic_comments}</p></div>}
            {infoSideSensors.length ? <SensorRegister title={infoSensorTitle} sensors={infoSideSensors} /> : <div className="monitor-empty compact-empty">No configured sensor channels are available.</div>}
        </div>
      </div>
        <div className="live-graphs-heading"><div><p className="section-index">DEMO DATA</p><h3>Sensor sample trends</h3></div><span>UP TO 60 SAMPLES RECEIVED IN THIS PAGE SESSION</span></div>
      <div className="sensor-chart-grid">
          {displayedSensors.length ? displayedSensors.map((sensor) => <SensorChart sensor={sensor} reading={reading} key={sensor.channel_key} />) : <div className="monitor-empty">No configured sensor channels are available.</div>}
      </div>
        <div className="sensor-tag-note">Charts contain only samples received during this page session. No historical plant data is stored or displayed here.</div>
    </section>
  );
}

function AlertLogTable({ alerts, loading, loadingMore, hasMore, selectedAlertId, onSelectAlert, onScroll, onLoadMore }) {
  if (loading) return <div className="monitor-empty">Loading alert log…</div>;
  if (!alerts.length) return <div className="monitor-empty">No alerts match this mill and date range.</div>;

  return (
    <div className="mill-alert-table-wrap" onScroll={onScroll}>
      <table className="mill-alert-table">
        <thead><tr><th>SELECT</th><th>ALERT ID</th><th>TIMESTAMP</th><th>SUBSYSTEM</th><th>SEVERITY</th><th>DIAGNOSTIC</th><th>SERVICING</th><th>CLASSIFICATION</th></tr></thead>
        <tbody>{alerts.map((alert) => (
          <tr key={alert.id} className={String(selectedAlertId) === String(alert.id) ? 'selected-alert-row' : ''}>
            <td><input aria-label={`Select alert ${alert.id}`} type="radio" name="alert-to-service" checked={String(selectedAlertId) === String(alert.id)} onChange={() => onSelectAlert(String(alert.id))} /></td>
            <td className="alert-id">#{alert.id}</td><td>{formatDate(alert.timestamp)}</td><td>{alert.equipment}</td>
            <td><span className={`severity-tag ${severityClass(alert.severity)}`}>{alert.severity}</span></td>
            <td className="mill-alert-diagnostic">{sanitizeAlertText(alert.issue) || '—'}</td><td>{alert.status || 'Status not recorded'}</td>
            <td>{alert.servicing_outcome?.replaceAll('_', ' ') || '—'}</td>
          </tr>
        ))}</tbody>
      </table>
      {loadingMore && <div className="alert-log-scroll-status">Loading older alerts…</div>}
      {!loadingMore && hasMore && <button className="alert-log-scroll-status" type="button" onClick={onLoadMore}>LOAD OLDER ALERTS</button>}
      {!hasMore && <div className="alert-log-scroll-status">All matching alerts loaded</div>}
    </div>
  );
}

function ServicingDesk({ backendUrl, mill, displayName }) {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const startDateInputRef = useRef(null);
  const endDateInputRef = useRef(null);
  const [page, setPage] = useState(0);
  const [alertData, setAlertData] = useState({ total: 0, alerts: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedAlertId, setSelectedAlertId] = useState('');
  const [servicedBy, setServicedBy] = useState('');
  const [outcome, setOutcome] = useState('GENUINE_ISSUE');
  const [serviceNotes, setServiceNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    const loadAlertLog = async () => {
      setLoading(true);
      setError('');
      const query = new URLSearchParams({ limit: String(ALERT_PAGE_SIZE), offset: String(page * ALERT_PAGE_SIZE) });
      if (startDate) query.set('start_date', startDate);
      if (endDate) query.set('end_date', endDate);
      try {
        const response = await fetch(`${getBackendBaseUrl(backendUrl)}/api/mills/${encodeURIComponent(mill)}/alerts?${query}`);
        if (!response.ok) throw new Error(`Alert request failed (${response.status})`);
        const result = await response.json();
        if (active) {
          setAlertData((current) => ({
            total: result.total,
            alerts: page === 0 ? result.alerts : [...current.alerts, ...result.alerts],
          }));
          setSelectedAlertId((selected) => page === 0 && !result.alerts.some((alert) => String(alert.id) === selected)
            ? String(result.alerts[0]?.id || '')
            : selected || String(result.alerts[0]?.id || ''));
        }
      } catch (requestError) {
        if (active) setError(requestError.message || 'Could not load this mill alert log.');
      } finally {
        if (active) setLoading(false);
      }
    };
    loadAlertLog();
    return () => { active = false; };
  }, [backendUrl, mill, page, refreshKey, startDate, endDate]);

  const exportQuery = new URLSearchParams();
  if (startDate) exportQuery.set('start_date', startDate);
  if (endDate) exportQuery.set('end_date', endDate);
  const exportUrl = `${getBackendBaseUrl(backendUrl)}/api/mills/${encodeURIComponent(mill)}/alerts/export.csv${exportQuery.size ? `?${exportQuery}` : ''}`;

  function openDatePicker(inputRef) {
    const input = inputRef.current;
    if (!input) return;
    if (typeof input.showPicker === 'function') input.showPicker();
    else {
      input.focus();
      input.click();
    }
  }

  async function submitService(event) {
    event.preventDefault();
    if (!selectedAlertId || servicedBy.trim().length < 2) {
      setNotice({ kind: 'error', text: 'Select an alert and enter at least two non-space characters for the servicing name.' });
      return;
    }
    setSubmitting(true);
    setNotice(null);
    try {
      const response = await fetch(`${getBackendBaseUrl(backendUrl)}/api/mills/${encodeURIComponent(mill)}/alerts/${selectedAlertId}/service`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ serviced_by: servicedBy.trim(), outcome, service_notes: serviceNotes.trim() }),
      });
      let result = {};
      try {
        result = await response.json();
      } catch {
        result = {};
      }
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : `Could not save servicing feedback (${response.status}).`);
      setNotice({ kind: 'success', text: result.model?.message || 'Service feedback saved.' });
      setServiceNotes('');
      setRefreshKey((key) => key + 1);
    } catch (submitError) {
      setNotice({ kind: 'error', text: submitError.message || 'Could not save servicing feedback.' });
    } finally {
      setSubmitting(false);
    }
  }

  const selectedAlert = alertData.alerts.find((alert) => String(alert.id) === String(selectedAlertId));
  const hasMoreAlerts = alertData.alerts.length < alertData.total;

  function handleAlertTableScroll(event) {
    const table = event.currentTarget;
    const nearBottom = table.scrollHeight - table.scrollTop - table.clientHeight < 80;
    if (nearBottom) loadMoreAlerts();
  }

  function loadMoreAlerts() {
    if (!loading && hasMoreAlerts) setPage((current) => current + 1);
  }

  return (
    <section className="monitor-view-content">
      <div className="monitor-section-heading"><div><p className="section-index">03 <span>/</span> SERVICE AND FEEDBACK</p><h2>{displayName || mill} servicing desk & alert log</h2></div><span className="section-context">{alertData.total.toLocaleString()} ALERTS</span></div>
      <div className="alert-period-toolbar">
        <div className="period-field"><button className="period-calendar-trigger" type="button" aria-label="Open start date calendar" onClick={() => openDatePicker(startDateInputRef)}><CalendarDays size={15} /></button><label htmlFor="alert-from">FROM</label><input ref={startDateInputRef} id="alert-from" type="date" max={endDate || undefined} value={startDate} onChange={(event) => { setStartDate(event.target.value); setPage(0); }} /></div>
        <div className="period-field"><button className="period-calendar-trigger" type="button" aria-label="Open end date calendar" onClick={() => openDatePicker(endDateInputRef)}><CalendarDays size={15} /></button><label htmlFor="alert-to">TO</label><input ref={endDateInputRef} id="alert-to" type="date" min={startDate || undefined} value={endDate} onChange={(event) => { setEndDate(event.target.value); setPage(0); }} /></div>
        <button className="subtle-action-button" type="button" onClick={() => { setStartDate(''); setEndDate(''); setPage(0); }}><RefreshCw size={14} /> CLEAR DATES</button>
        <a className="export-button" href={exportUrl}><Download size={15} /> DOWNLOAD CSV</a>
      </div>
      <div className="alert-provenance-note">Historical alert records do not include source tracking. Verify their origin before treating them as operational events; demo telemetry no longer writes alerts to this register.</div>
      {error && <div className="monitor-error">{error}</div>}
      <AlertLogTable alerts={alertData.alerts} loading={loading && !alertData.alerts.length} loadingMore={loading && alertData.alerts.length > 0} hasMore={hasMoreAlerts} selectedAlertId={selectedAlertId} onSelectAlert={setSelectedAlertId} onScroll={handleAlertTableScroll} onLoadMore={loadMoreAlerts} />
      <form className="servicing-form" onSubmit={submitService}>
        <div className="service-form-heading"><div><p className="section-index">FEEDBACK LOOP</p><h3>Record servicing outcome</h3></div><Wrench size={18} /></div>
        <div className="selected-alert-summary"><span>SELECTED ALERT</span><strong>{selectedAlert ? `#${selectedAlert.id} · ${selectedAlert.equipment}` : 'Select an alert from the table'}</strong><small>{selectedAlert ? `${formatDate(selectedAlert.timestamp)} · ${sanitizeAlertText(selectedAlert.issue) || 'No diagnostic recorded'}` : 'Choose a row above or use the selection control.'}</small></div>
        <div className="service-form-fields">
          <label>ALERT TO SERVICE<select value={selectedAlertId} onChange={(event) => setSelectedAlertId(event.target.value)} required><option value="" disabled>Select an alert</option>{alertData.alerts.map((alert) => <option key={alert.id} value={alert.id}>#{alert.id} · {alert.equipment} · {formatDate(alert.timestamp)}</option>)}</select></label>
          <label>PERSON SERVICING<input value={servicedBy} onChange={(event) => setServicedBy(event.target.value)} minLength={2} maxLength={120} placeholder="Enter operator or technician name" required /></label>
        </div>
        <fieldset className="outcome-fieldset"><legend>SERVICING CLASSIFICATION</legend>
          <label className={`outcome-option ${outcome === 'GENUINE_ISSUE' ? 'outcome-selected' : ''}`}><input type="radio" name="servicing-outcome" value="GENUINE_ISSUE" checked={outcome === 'GENUINE_ISSUE'} onChange={(event) => setOutcome(event.target.value)} /><span className="outcome-check"><Check size={13} /></span><span><strong>Genuine Issue</strong><small>Confirmed failure / wear</small></span></label>
          <label className={`outcome-option ${outcome === 'FALSE_ALARM' ? 'outcome-selected' : ''}`}><input type="radio" name="servicing-outcome" value="FALSE_ALARM" checked={outcome === 'FALSE_ALARM'} onChange={(event) => setOutcome(event.target.value)} /><span className="outcome-check"><Check size={13} /></span><span><strong>False Alarm</strong><small>Operational spike</small></span></label>
        </fieldset>
        <label className="service-notes-field">SERVICE NOTES<textarea value={serviceNotes} onChange={(event) => setServiceNotes(event.target.value)} maxLength={2000} rows={3} placeholder="Describe inspection findings or work performed" /></label>
        <div className="service-submit-row"><p>Feedback is recorded for review; model updates are disabled until sensor tags and calibration data are verified.</p><button className="submit-service-button" type="submit" disabled={submitting || loading || !alertData.alerts.length}>{submitting ? 'SAVING…' : 'SAVE SERVICE FEEDBACK'}</button></div>
        {notice && <div className={`service-notice ${notice.kind === 'error' ? 'service-notice-error' : ''}`} role={notice.kind === 'error' ? 'alert' : 'status'}>{notice.text}</div>}
      </form>
    </section>
  );
}

export default function IndividualMillMonitor({ mills = [], backendUrl, initialMill }) {
  const [mill, setMill] = useState(initialMill || mills[0] || '');
  const [millDisplayName, setMillDisplayName] = useState(initialMill || mills[0] || '');
  const [view, setView] = useState(MONITOR_VIEWS[0]);
  const [equipmentList, setEquipmentList] = useState([]);
  const [equipmentConfig, setEquipmentConfig] = useState({});
  const [inventoryStatus, setInventoryStatus] = useState('LOADING');
  const [selectedEquipment, setSelectedEquipment] = useState('');
  const [readings, setReadings] = useState({});
  const [equipmentError, setEquipmentError] = useState('');

  useEffect(() => {
    if (!mill && (initialMill || mills[0])) {
      const initial = initialMill || mills[0];
      setMill(initial);
      setMillDisplayName(initial);
    }
  }, [mill, initialMill, mills]);

  useEffect(() => {
    if (!mill) return undefined;
    let active = true;
    setEquipmentList([]);
    setEquipmentConfig({});
    setInventoryStatus('LOADING');
    setSelectedEquipment('');
    setReadings({});
    setMillDisplayName(mill);
    fetch(`${getBackendBaseUrl(backendUrl)}/api/mills/${encodeURIComponent(mill)}/inventory`)
      .then((response) => {
        if (!response.ok) throw new Error(`Inventory request failed (${response.status})`);
        return response.json();
      })
      .then((inventory) => {
        if (!active) return;
        const assets = Array.isArray(inventory.equipment) ? inventory.equipment : [];
        const names = assets.map((asset) => asset.name);
        setEquipmentList(names);
        setEquipmentConfig(Object.fromEntries(assets.map((asset) => [asset.name, asset.sensors || []])));
        setInventoryStatus(inventory.status || 'NOT_CONFIGURED');
        setMillDisplayName(inventory.display_name || mill);
        setSelectedEquipment(names[0] || '');
        setEquipmentError('');
      })
      .catch((requestError) => {
        if (!active) return;
        setInventoryStatus('UNAVAILABLE');
        setEquipmentError(requestError.message || 'Could not load equipment inventory.');
      });
    return () => { active = false; };
  }, [backendUrl, mill]);

  useEffect(() => {
    if (!equipmentList.length) return undefined;
    let active = true;
    const sockets = equipmentList.map((equipment) => {
      const url = `${getWebSocketBaseUrl(backendUrl)}/ws/telemetry/${encodeURIComponent(mill)}/${encodeURIComponent(equipment)}`;
      const socket = new WebSocket(url);
      setReadings((current) => ({ ...current, [equipment]: { ...(current[equipment] || {}), status: 'CONNECTING TO DEMO FEED' } }));
      socket.onopen = () => {
        if (active) setReadings((current) => ({ ...current, [equipment]: { ...(current[equipment] || {}), status: 'CONNECTED · WAITING FOR DEMO DATA' } }));
      };
      socket.onmessage = (event) => {
        if (!active) return;
        let payload;
        try {
          payload = JSON.parse(event.data);
        } catch {
          setReadings((current) => ({ ...current, [equipment]: { ...(current[equipment] || {}), status: 'INVALID DEMO MESSAGE' } }));
          return;
        }
        if (!Array.isArray(payload.sensors)) {
          setReadings((current) => ({ ...current, [equipment]: { ...(current[equipment] || {}), status: 'DEMO CHANNELS UNAVAILABLE' } }));
          return;
        }
        setReadings((current) => {
          const previous = current[equipment] || {};
          const sampleTime = payload.sample_time || new Date().toISOString();
          const sample = {
            sample_time: sampleTime,
            values: Object.fromEntries(payload.sensors.map((sensor) => [sensor.channel_key, Number(sensor.value)])),
          };
          return {
            ...current,
            [equipment]: {
              ...previous,
              status: 'CONNECTED · DEMO DATA',
              sensors: payload.sensors,
              prediction: payload.prediction,
              sampleTime,
              receivedAt: Date.now(),
              samples: [...(previous.samples || []), sample].slice(-60),
            },
          };
        });
      };
      socket.onerror = () => {
        if (active) setReadings((current) => ({ ...current, [equipment]: { ...(current[equipment] || {}), status: 'DEMO CONNECTION ERROR' } }));
      };
      socket.onclose = () => {
        if (active) setReadings((current) => ({ ...current, [equipment]: { ...(current[equipment] || {}), status: 'DEMO FEED DISCONNECTED' } }));
      };
      return socket;
    });

    return () => {
      active = false;
      sockets.forEach((socket) => socket.close());
    };
  }, [backendUrl, equipmentList, mill]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setReadings((current) => {
        let changed = false;
        const next = { ...current };
        Object.entries(current).forEach(([equipment, reading]) => {
          if (reading.status === 'CONNECTED · DEMO DATA' && reading.receivedAt && Date.now() - reading.receivedAt > 5000) {
            next[equipment] = { ...reading, status: 'STALE DEMO DATA' };
            changed = true;
          }
        });
        return changed ? next : current;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  const selectedReading = useMemo(() => readings[selectedEquipment] || {}, [readings, selectedEquipment]);

  return (
    <div className="dashboard mill-monitor-dashboard">
      <section className="page-heading monitor-page-heading">
        <div><p className="eyebrow">PLANT OPERATIONS <span>/</span> INDIVIDUAL MILL MONITOR</p><h1>{millDisplayName || 'Mill condition'} monitor</h1><p className="page-subtitle">Subsystem status, sensor detail and maintenance feedback</p></div>
        <label className="mill-select-label" htmlFor="mill-unit-select">SELECT MILL UNIT<select id="mill-unit-select" value={mill} onChange={(event) => setMill(event.target.value)}>{!mills.length && <option value="">Mill list unavailable</option>}{mills.map((unit) => <option value={unit} key={unit}>{unit}</option>)}</select></label>
      </section>
      <nav className="monitor-tabs" aria-label="Individual mill monitor pages">{MONITOR_VIEWS.map((tab, index) => <button className={view === tab ? 'monitor-tab-active' : ''} key={tab} type="button" onClick={() => setView(tab)}><span>0{index + 1}</span>{tab}</button>)}</nav>
      {equipmentError && <div className="monitor-error"><AlertTriangle size={15} /> {equipmentError}</div>}
      {view === MONITOR_VIEWS[0] && <SubsystemOverview mill={mill} displayName={millDisplayName} inventoryStatus={inventoryStatus} equipmentList={equipmentList} equipmentConfig={equipmentConfig} readings={readings} onSelectSubsystem={(equipment) => { setSelectedEquipment(equipment); setView(MONITOR_VIEWS[1]); }} />}
      {view === MONITOR_VIEWS[1] && <EquipmentDrillDown mill={mill} displayName={millDisplayName} inventoryStatus={inventoryStatus} equipmentList={equipmentList} equipmentConfig={equipmentConfig} selectedEquipment={selectedEquipment} onEquipmentChange={setSelectedEquipment} reading={selectedReading} />}
      {view === MONITOR_VIEWS[2] && <ServicingDesk key={mill} backendUrl={backendUrl} mill={mill} displayName={millDisplayName} />}
      <footer className="page-footer">OPERATIONS INTELLIGENCE <span>•</span> LAFARGEHOLCIM CÔTE D'IVOIRE <span>•</span> &copy; {new Date().getFullYear()} All rights reserved <span>•</span> Developed by Wirkuu Justice S</footer>
    </div>
  );
}