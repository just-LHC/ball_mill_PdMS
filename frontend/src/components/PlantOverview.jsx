import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Activity, AlertTriangle, ArrowDown, ArrowUp, Check, ChevronRight, Clock3, Factory, MoreVertical, RefreshCw, ShieldAlert } from 'lucide-react';
import { getBackendBaseUrl } from '../api';
import { sanitizeAlertText } from '../alertText';

const REFRESH_INTERVAL = 30000;
const PAGE_SIZE = 10;
const ALERT_COLUMNS = [
	{ id: 'id', label: 'Alert ID', type: 'number', width: 100, value: (alert) => alert.id },
	{ id: 'timestamp', label: 'Timestamp', type: 'date', width: 175, value: (alert) => alert.timestamp },
	{ id: 'mill', label: 'Mill', type: 'text', width: 125, value: (alert) => alert.mill },
	{ id: 'equipment', label: 'Equipment Subsystem', type: 'text', width: 190, value: (alert) => alert.equipment },
	{ id: 'severity', label: 'Severity', type: 'severity', width: 115, value: (alert) => alert.severity },
	{ id: 'diagnostic', label: 'Root Cause Diagnostic', type: 'text', width: 265, value: getDiagnostic },
	{ id: 'action', label: 'Recommended Action', type: 'text', width: 265, value: getRecommendedAction },
	{ id: 'status', label: 'Servicing Status', type: 'text', width: 175, value: (alert) => alert.status },
];

function getFormatOptions(type) {
	if (type === 'number') return [{ id: 'default', label: 'Plain number' }, { id: 'grouped', label: 'Grouped number' }];
	if (type === 'date') return [{ id: 'default', label: 'Local date & time' }, { id: 'date-only', label: 'Date only' }, { id: 'iso', label: 'ISO timestamp' }];
	if (type === 'severity') return [{ id: 'default', label: 'Uppercase' }, { id: 'title', label: 'Title case' }, { id: 'lowercase', label: 'Lowercase' }];
	return [{ id: 'default', label: 'As stored' }, { id: 'uppercase', label: 'UPPERCASE' }, { id: 'lowercase', label: 'lowercase' }];
}

function formatColumnValue(column, alert, format) {
	const value = column.value(alert);
	if (value === null || value === undefined || value === '') return '—';
	if (column.type === 'number') {
		const number = Number(value);
		return Number.isFinite(number) ? (format === 'grouped' ? number.toLocaleString() : String(number)) : String(value);
	}
	if (column.type === 'date') {
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return String(value);
		if (format === 'date-only') return date.toLocaleDateString();
		if (format === 'iso') return date.toISOString();
		return date.toLocaleString();
	}
	const text = String(value);
	if (format === 'uppercase') return text.toLocaleUpperCase();
	if (format === 'lowercase') return text.toLocaleLowerCase();
	if (column.type === 'severity' && format === 'title') return text.toLocaleLowerCase().replace(/\b\w/g, (letter) => letter.toLocaleUpperCase());
	return text;
}

function getColumnStatistics(column, alerts) {
	const values = alerts.map(column.value).filter((value) => value !== null && value !== undefined && value !== '');
	if (column.type === 'number' && values.length) {
		const numbers = values.map(Number).filter(Number.isFinite);
		if (numbers.length) {
			return [
				['Values', numbers.length],
				['Minimum', Math.min(...numbers).toLocaleString()],
				['Maximum', Math.max(...numbers).toLocaleString()],
				['Average', (numbers.reduce((total, value) => total + value, 0) / numbers.length).toLocaleString(undefined, { maximumFractionDigits: 2 })],
			];
		}
	}
	if (column.type === 'date' && values.length) {
		const dates = values.map((value) => new Date(value).getTime()).filter(Number.isFinite);
		if (dates.length) return [['Values', dates.length], ['Oldest', new Date(Math.min(...dates)).toLocaleDateString()], ['Newest', new Date(Math.max(...dates)).toLocaleDateString()]];
	}
	const frequency = new Map();
	values.forEach((value) => {
		const label = String(value);
		frequency.set(label, (frequency.get(label) || 0) + 1);
	});
	const topValues = [...frequency.entries()].sort((left, right) => right[1] - left[1]).slice(0, 3);
	return [['Values', values.length], ['Unique', frequency.size], ...topValues.map(([label, count]) => [label, count])];
}

function getSeverity(alert) {
	return String(alert.severity || '').toUpperCase();
}

function formatTimestamp(value) {
	if (!value) return 'Timestamp unavailable';
	const date = new Date(value);
	return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function getDiagnostic(alert) {
	return sanitizeAlertText(alert.root_cause_diagnostic || alert.diagnostic_comments || alert.issue || 'No diagnostic was recorded.');
}

function getModelScore(alert) {
	const value = alert.model_score ?? alert.anomaly_score;
	if (value === null || value === undefined || value === '') return null;
	const score = Number(value);
	return Number.isFinite(score) ? score : null;
}

function getRecommendedAction(alert) {
	return alert.recommended_action || 'No recommended action was recorded.';
}

function formatReading(value, unit) {
	if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value))) return null;
	return `${Number(value).toFixed(1)} ${unit}`;
}

function normalizeOverviewResponse(payload) {
	if (!payload || typeof payload !== 'object') return { total_count: 0, critical_count: 0, warning_count: 0, critical_alerts: [], alerts: [] };
	const data = payload.data && typeof payload.data === 'object' ? payload.data : payload;
	const alerts = Array.isArray(data.alerts) ? data.alerts : Array.isArray(payload.alerts) ? payload.alerts : [];
	const criticalAlerts = Array.isArray(data.critical_alerts) ? data.critical_alerts : Array.isArray(payload.critical_alerts) ? payload.critical_alerts : [];
	return {
		total_count: Number(data.total_count ?? payload.total_count ?? alerts.length ?? 0) || 0,
		critical_count: Number(data.critical_count ?? payload.critical_count ?? criticalAlerts.length ?? 0) || 0,
		warning_count: Number(data.warning_count ?? payload.warning_count ?? 0) || 0,
		critical_alerts: criticalAlerts,
		alerts,
	};
}

function mergeUniqueAlerts(...batches) {
	const seen = new Set();
	return batches.flat().filter((alert) => {
		const key = String(alert.id ?? `${alert.timestamp}|${alert.mill}|${alert.equipment}|${alert.severity}`);
		if (seen.has(key)) return false;
		seen.add(key);
		return true;
	});
}

function MillCount({ mills }) {
	return (
		<div className="mill-count-list" aria-label="Mills included in the system">
			{mills.map((mill) => <span key={mill}>{mill.replace('Mill ', 'M')}</span>)}
		</div>
	);
}

function PredictionCard({ alert }) {
	const score = getModelScore(alert);
	const vibration = formatReading(alert.vibration_snapshot, 'mm/s');
	const temperature = formatReading(alert.temperature_snapshot, '°C');

	return (
		<article className="prediction-card">
			<div className="prediction-card-top">
				<span className="prediction-mill">{alert.mill || 'Mill not recorded'} <span>/</span> {alert.equipment || 'Subsystem not recorded'}</span>
				<span className="severity-tag severity-critical">CRITICAL</span>
			</div>
			<div className="prediction-signal">
				<div>
					<p className="prediction-label">RECORDED DIAGNOSTIC</p>
					<p className="prediction-diagnostic">{getDiagnostic(alert)}</p>
				</div>
				<div className="model-score-value">{score === null ? '—' : score.toFixed(3)}<span>{score === null ? 'SCORE NOT RECORDED' : 'UNCALIBRATED SCORE'}</span></div>
			</div>
			{(vibration || temperature) && (
				<div className="prediction-readings">
					{vibration && <span>Vibration <strong>{vibration}</strong></span>}
					{temperature && <span>Bearing temp <strong>{temperature}</strong></span>}
				</div>
			)}
			<div className="prediction-action"><span>RECORDED ACTION</span>{getRecommendedAction(alert)}</div>
			<div className="prediction-time"><Clock3 size={13} /> {formatTimestamp(alert.timestamp)}</div>
		</article>
	);
}

function AlertTable({ alerts, loading, error, loadingMore, loadMoreError, hasMore, onScroll, onLoadMore }) {
	if (loading && !alerts.length) return <div className="table-message">Loading alert records…</div>;
	if (error && !alerts.length) return <div className="table-message table-error">Alert storage is unavailable. Configure DATABASE_URL and verify database connectivity, then refresh.</div>;
	if (alerts.length === 0) return <div className="table-message">No alerts have been recorded.</div>;
	return <AlertRegisterTable alerts={alerts} loadingMore={loadingMore} loadMoreError={loadMoreError} hasMore={hasMore} onScroll={onScroll} onLoadMore={onLoadMore} />;
}

function AlertRegisterTable({ alerts, loadingMore, loadMoreError, hasMore, onScroll, onLoadMore }) {
	const [sort, setSort] = useState(null);
	const [openMenu, setOpenMenu] = useState(null);
	const [statisticsColumn, setStatisticsColumn] = useState(null);
	const [formatColumn, setFormatColumn] = useState(null);
	const [formats, setFormats] = useState({});
	const [widths, setWidths] = useState(() => Object.fromEntries(ALERT_COLUMNS.map((column) => [column.id, column.width])));
	const [pinnedColumns, setPinnedColumns] = useState(() => new Set());
	const menuRef = useRef(null);

	useEffect(() => {
		if (!openMenu) return undefined;
		const closeOnOutsideClick = (event) => {
			if (!menuRef.current?.contains(event.target)) setOpenMenu(null);
		};
		const closeOnEscape = (event) => {
			if (event.key === 'Escape') setOpenMenu(null);
		};
		document.addEventListener('pointerdown', closeOnOutsideClick);
		document.addEventListener('keydown', closeOnEscape);
		return () => {
			document.removeEventListener('pointerdown', closeOnOutsideClick);
			document.removeEventListener('keydown', closeOnEscape);
		};
	}, [openMenu]);

	const sortedAlerts = useMemo(() => {
		if (!sort) return alerts;
		const column = ALERT_COLUMNS.find((item) => item.id === sort.id);
		if (!column) return alerts;
		const direction = sort.direction === 'ascending' ? 1 : -1;
		return [...alerts].sort((left, right) => {
			const leftValue = column.value(left);
			const rightValue = column.value(right);
			if (leftValue === null || leftValue === undefined) return rightValue === null || rightValue === undefined ? 0 : 1;
			if (rightValue === null || rightValue === undefined) return -1;
			if (column.type === 'number') return (Number(leftValue) - Number(rightValue)) * direction;
			if (column.type === 'date') return (new Date(leftValue).getTime() - new Date(rightValue).getTime()) * direction;
			return String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: 'base' }) * direction;
		});
	}, [alerts, sort]);

	const pinOffsets = {};
	let nextPinnedOffset = 0;
	ALERT_COLUMNS.forEach((column) => {
		if (pinnedColumns.has(column.id)) {
			pinOffsets[column.id] = nextPinnedOffset;
			nextPinnedOffset += widths[column.id];
		}
	});

	function closeMenu() {
		setOpenMenu(null);
		setStatisticsColumn(null);
		setFormatColumn(null);
	}

	function autosizeColumn(column) {
		const longestValue = Math.max(column.label.length, ...alerts.map((alert) => String(column.value(alert) ?? '').length));
		setWidths((current) => ({ ...current, [column.id]: Math.max(100, Math.min(460, longestValue * 7 + 48)) }));
		closeMenu();
	}

	function togglePinnedColumn(columnId) {
		setPinnedColumns((current) => {
			const next = new Set(current);
			if (next.has(columnId)) next.delete(columnId);
			else next.add(columnId);
			return next;
		});
		closeMenu();
	}

	return (
		<div className="alert-table-scroll" onScroll={onScroll}>
			<table className="alert-table">
				<colgroup>{ALERT_COLUMNS.map((column) => <col key={column.id} style={{ width: `${widths[column.id]}px` }} />)}</colgroup>
				<thead>
					<tr>
						{ALERT_COLUMNS.map((column) => {
							const pinned = pinnedColumns.has(column.id);
							const activeFormat = formats[column.id] || 'default';
							return (
								<th className={pinned ? 'alert-column-pinned' : ''} key={column.id} style={pinned ? { left: `${pinOffsets[column.id]}px` } : undefined}>
									<div className="alert-column-heading">
										<span className="alert-column-label">{column.label}{sort?.id === column.id && (sort.direction === 'ascending' ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}</span>
										<div className="column-menu-wrap" ref={openMenu === column.id ? menuRef : null}>
											<button className="column-menu-trigger" type="button" aria-label={`Column actions for ${column.label}`} aria-haspopup="menu" aria-expanded={openMenu === column.id} title={`Column actions for ${column.label}`} onClick={() => { setOpenMenu(openMenu === column.id ? null : column.id); setStatisticsColumn(null); setFormatColumn(null); }}><MoreVertical size={15} /></button>
											{openMenu === column.id && (
												<div className="column-menu" role="menu" aria-label={`${column.label} column actions`} onPointerDown={(event) => event.stopPropagation()}>
												<div className="column-menu-title"><strong>{column.id}</strong><span>{column.label}</span></div>
												<button role="menuitem" type="button" onClick={() => { setSort({ id: column.id, direction: 'ascending' }); closeMenu(); }}><ArrowUp size={14} /> Sort ascending</button>
												<button role="menuitem" type="button" onClick={() => { setSort({ id: column.id, direction: 'descending' }); closeMenu(); }}><ArrowDown size={14} /> Sort descending</button>
												<button role="menuitem" type="button" aria-expanded={statisticsColumn === column.id} onClick={() => { setStatisticsColumn(statisticsColumn === column.id ? null : column.id); setFormatColumn(null); }}><Activity size={14} /> Statistics</button>
												{statisticsColumn === column.id && <div className="column-menu-detail"><span className="column-menu-detail-title">CURRENT PAGE STATISTICS</span>{getColumnStatistics(column, alerts).map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>}
												<button role="menuitem" type="button" aria-expanded={formatColumn === column.id} onClick={() => { setFormatColumn(formatColumn === column.id ? null : column.id); setStatisticsColumn(null); }}><span className="column-menu-button-icon">Aa</span> Format <ChevronRight size={13} /></button>
												{formatColumn === column.id && <div className="column-menu-formats">{getFormatOptions(column.type).map((option) => <button className={(formats[column.id] || 'default') === option.id ? 'column-format-selected' : ''} key={option.id} type="button" onClick={() => setFormats((current) => ({ ...current, [column.id]: option.id }))}>{option.label}{(formats[column.id] || 'default') === option.id && <Check size={13} />}</button>)}</div>}
												<div className="column-menu-divider" />
												<button role="menuitem" type="button" onClick={() => autosizeColumn(column)}><span className="column-menu-button-icon">↔</span> Autosize</button>
												<button role="menuitem" type="button" onClick={() => togglePinnedColumn(column.id)}><span className="column-menu-button-icon">{pinned ? '↤' : '↦'}</span> {pinned ? 'Unpin column' : 'Pin column'}</button>
											</div>
											)}
										</div>
									</div>
								</th>
							);
						})}
					</tr>
				</thead>
				<tbody>
					{sortedAlerts.map((alert, index) => {
						return (
							<tr key={alert.id ?? `${alert.mill}-${alert.timestamp}-${index}`}>
								{ALERT_COLUMNS.map((column) => {
									const pinned = pinnedColumns.has(column.id);
									const formattedValue = formatColumnValue(column, alert, formats[column.id] || 'default');
									const severity = getSeverity(alert);
									return <td className={`${column.id === 'id' ? 'alert-id' : ''} ${column.id === 'timestamp' ? 'timestamp-cell' : ''} ${column.id === 'diagnostic' || column.id === 'action' ? 'diagnostic-cell' : ''} ${pinned ? 'alert-column-pinned' : ''}`} key={column.id} style={pinned ? { left: `${pinOffsets[column.id]}px` } : undefined} title={String(column.value(alert) ?? '')}>{column.type === 'severity' ? <span className={`severity-tag ${severity === 'CRITICAL' ? 'severity-critical' : severity === 'WARNING' ? 'severity-warning' : 'severity-neutral'}`}>{formattedValue}</span> : column.id === 'id' && formattedValue !== '—' ? `#${formattedValue}` : formattedValue}</td>;
								})}
							</tr>
						);
					})}
				</tbody>
			</table>
			{loadingMore && <div className="alert-register-scroll-status">Loading older alerts…</div>}
			{!loadingMore && hasMore && <button className="alert-register-scroll-status" type="button" onClick={onLoadMore}>{loadMoreError ? 'RETRY LOADING OLDER ALERTS' : 'LOAD OLDER ALERTS'}</button>}
			{!loadingMore && !hasMore && <div className="alert-register-scroll-status">All matching alerts loaded</div>}
		</div>
	);
}

export default function PlantOverview({ mills = [], backendUrl, onOpenMill }) {
	const [overview, setOverview] = useState(null);
	const [loading, setLoading] = useState(true);
	const [loadingMore, setLoadingMore] = useState(false);
	const [error, setError] = useState(false);
	const [loadMoreError, setLoadMoreError] = useState(false);
	const [page, setPage] = useState(0);
	const [refreshKey, setRefreshKey] = useState(0);
	const [lastUpdated, setLastUpdated] = useState(null);
	const alertCursor = useRef(null);

	useEffect(() => {
		let active = true;

		const loadAlerts = async () => {
			if (page === 0) setLoading(true);
			else setLoadingMore(true);
			setLoadMoreError(false);
			try {
				const offset = page * PAGE_SIZE;
				const backendBaseUrl = getBackendBaseUrl(backendUrl);
				const query = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(page === 0 || !alertCursor.current ? offset : 0) });
				if (page > 0 && alertCursor.current) {
					query.set('before_timestamp', alertCursor.current.timestamp);
					query.set('before_id', String(alertCursor.current.id));
				}
				const response = await fetch(`${backendBaseUrl}/api/overview?${query}`);
				if (!response.ok) throw new Error(`Alert request failed: ${response.status}`);
				const result = await response.json();
				const normalized = normalizeOverviewResponse(result);
				if (active) {
					if ((normalized.alerts.length === 0 || normalized.critical_alerts.length === 0) && normalized.total_count > 0) {
						const fallbackResponse = await fetch(`${backendBaseUrl}/api/alerts`);
						if (fallbackResponse.ok) {
							const fallbackPayload = await fallbackResponse.json();
							const fallbackAlerts = Array.isArray(fallbackPayload) ? fallbackPayload : fallbackPayload.alerts || [];
							const cursor = page > 0 ? alertCursor.current : null;
							const fallbackPage = cursor ? fallbackAlerts.filter((alert) => {
								const timestampDifference = new Date(alert.timestamp).getTime() - new Date(cursor.timestamp).getTime();
								return timestampDifference < 0 || (timestampDifference === 0 && Number(alert.id) < Number(cursor.id));
							}) : fallbackAlerts.slice(offset);
							const pagedAlerts = fallbackPage.slice(0, PAGE_SIZE);
							const critAlerts = fallbackAlerts.filter((alert) => String(alert.severity || '').toUpperCase() === 'CRITICAL').slice(0, 3);
							normalized.alerts = pagedAlerts;
							normalized.critical_alerts = critAlerts;
							normalized.total_count = fallbackAlerts.length;
							normalized.warning_count = fallbackAlerts.filter((alert) => String(alert.severity || '').toUpperCase() === 'WARNING').length;
							normalized.critical_count = critAlerts.length;
						}
					}
					const lastAlert = normalized.alerts.at(-1);
					alertCursor.current = lastAlert ? { timestamp: lastAlert.timestamp, id: lastAlert.id } : null;
					setOverview((current) => page === 0
						? normalized
						: { ...normalized, alerts: mergeUniqueAlerts(current?.alerts || [], normalized.alerts) });
					setLastUpdated(new Date());
					setError(false);
				}
			} catch {
				if (active) {
					if (page === 0) {
						setOverview(null);
						setError(true);
					} else {
						setLoadMoreError(true);
					}
				}
			} finally {
				if (active) {
					setLoading(false);
					setLoadingMore(false);
				}
			}
		};

		loadAlerts();
		return () => {
			active = false;
		};
	}, [backendUrl, page, refreshKey]);

	useEffect(() => {
		const interval = window.setInterval(() => {
			setPage(0);
			setRefreshKey((key) => key + 1);
		}, REFRESH_INTERVAL);
		return () => window.clearInterval(interval);
	}, []);

	const alerts = overview?.alerts || [];
	const latestCritical = overview?.critical_alerts || [];
	const totalCount = overview?.total_count || 0;
	const criticalCount = overview?.critical_count || 0;
	const warningCount = overview?.warning_count || 0;
	const hasMoreAlerts = alerts.length < totalCount;

	function loadMoreAlerts() {
		if (loading || loadingMore || !hasMoreAlerts) return;
		if (loadMoreError) {
			setRefreshKey((key) => key + 1);
			return;
		}
		setPage((current) => current + 1);
	}

	function handleAlertTableScroll(event) {
		const table = event.currentTarget;
		if (table.scrollHeight - table.scrollTop - table.clientHeight < 80) loadMoreAlerts();
	}

	return (
		<div className="dashboard overview-dashboard" id="overview">
			<section className="page-heading overview-heading">
				<div>
					<p className="eyebrow">PLANT OPERATIONS <span>/</span> ABIDJAN</p>
					<h1>Plant General Overview</h1>
					<p className="page-subtitle">Mill health, critical events and maintenance alerts</p>
				</div>
				<button className="refresh-button" type="button" onClick={() => { setLoading(true); setPage(0); setRefreshKey((key) => key + 1); }} aria-label="Refresh alert data" title="Refresh alert data">
					<RefreshCw size={15} /> <span>REFRESH</span>
				</button>
			</section>

			<section className={`priority-strip ${latestCritical.length ? 'priority-has-critical' : 'priority-no-critical'}`} aria-live="polite">
				<div className="priority-icon"><ShieldAlert size={21} /></div>
				<div className="priority-content">
					<span className="priority-kicker">LATEST CRITICAL EVENT</span>
					<strong>{loading && !overview ? 'Loading latest event…' : error ? 'Alert feed unavailable' : latestCritical[0] ? `${latestCritical[0].mill || 'Mill not recorded'} · ${latestCritical[0].equipment || 'Subsystem not recorded'}` : 'No critical alerts recorded'}</strong>
					{latestCritical[0] && !error && <p>{getDiagnostic(latestCritical[0])}</p>}
					{latestCritical[0] && !error && <span className="priority-model-score">MODEL SCORE <strong>{getModelScore(latestCritical[0]) === null ? 'Not recorded' : `${getModelScore(latestCritical[0]).toFixed(3)} · uncalibrated`}</strong></span>}
					<span className="priority-time">{lastUpdated ? `Data refreshed ${lastUpdated.toLocaleTimeString()}` : 'Waiting for alert data'}</span>
				</div>
				<div className="priority-side">
					<div className="priority-count"><strong>{loading && !overview ? '—' : criticalCount.toLocaleString()}</strong><span>CRITICAL<br />ALERTS</span></div>
					{latestCritical[0] && !error && <button type="button" onClick={() => onOpenMill?.(latestCritical[0].mill)}>OPEN MILL MONITOR</button>}
				</div>
			</section>

			<section className="overview-stats" aria-label="System summary">
				<article className="overview-stat mill-stat">
					<div className="stat-topline"><span>MILL UNITS</span><Factory size={16} /></div>
					<div className="stat-number">{mills.length}</div>
					<MillCount mills={mills} />
				</article>
				<article className="overview-stat total-stat">
					<div className="stat-topline"><span>ALERTS AVAILABLE</span><Activity size={16} /></div>
					<div className="stat-number">{loading && !overview ? '—' : totalCount.toLocaleString()}</div>
					<div className="stat-caption">Logged across all mill units</div>
				</article>
				<article className="overview-stat critical-stat">
					<div className="stat-topline"><span>CRITICAL ALERTS</span><ShieldAlert size={16} /></div>
					  <div className="stat-number">{loading && !overview ? '—' : criticalCount.toLocaleString()}</div>
					<div className="stat-caption">Require immediate attention</div>
				</article>
				<article className="overview-stat warning-stat">
					<div className="stat-topline"><span>WARNING ALERTS</span><AlertTriangle size={16} /></div>
					  <div className="stat-number">{loading && !overview ? '—' : warningCount.toLocaleString()}</div>
					<div className="stat-caption">Monitor and plan intervention</div>
				</article>
			</section>

			<section className="overview-section">
				<div className="overview-section-heading">
					<div><p className="section-index">01 <span>/</span> CRITICAL ALERTS</p><h2>Recent critical alerts</h2></div>
					  <span className="section-context">LATEST {latestCritical.length} OF {criticalCount.toLocaleString()} CRITICAL</span>
				</div>
				{loading ? (
					<div className="prediction-empty">Loading critical alert predictions…</div>
				) : latestCritical.length ? (
					<div className="prediction-grid">{latestCritical.map((alert, index) => <PredictionCard key={alert.id ?? index} alert={alert} />)}</div>
				) : (
					<div className="prediction-empty">No critical alerts are currently available.</div>
				)}
			</section>

			<section className="overview-section alerts-section">
				<div className="overview-section-heading">
					<div><p className="section-index">02 <span>/</span> MAINTENANCE QUEUE</p><h2>Alert register</h2></div>
					<span className="section-context">{loading && !overview ? 'LOADING' : `${totalCount.toLocaleString()} RECORDS`}</span>
				</div>
				<div className="alert-provenance-note">Historical alert records do not include source tracking. Verify their origin before treating them as operational events; demo telemetry no longer writes alerts to this register.</div>
				<AlertTable alerts={alerts} loading={loading} error={error} loadingMore={loadingMore} loadMoreError={loadMoreError} hasMore={hasMoreAlerts} onScroll={handleAlertTableScroll} onLoadMore={loadMoreAlerts} />
			</section>

			<footer className="page-footer">OPERATIONS INTELLIGENCE <span>•</span> LAFARGEHOLCIM CÔTE D'IVOIRE <span>•</span> &copy; {new Date().getFullYear()} All rights reserved <span>•</span> Developed by Wirkuu Justice S</footer>
		</div>
	);
}
