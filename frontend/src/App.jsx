import React, { useEffect, useState } from 'react';
import { Activity, Factory } from 'lucide-react';
import logo from '../photos/lafargeholcim_cte_d_ivoire_logo.jpg';
import { getBackendBaseUrl } from './api';
import IndividualMillMonitor from './components/IndividualMillMonitor';
import PlantOverview from './components/PlantOverview';

export default function App() {
  const [activePage, setActivePage] = useState('overview');
  const [mills, setMills] = useState([]);
  const [selectedMill, setSelectedMill] = useState('');
  const [millLoadError, setMillLoadError] = useState('');
  const backendUrl = import.meta.env.VITE_BACKEND_URL;

  useEffect(() => {
    let active = true;
    fetch(`${getBackendBaseUrl(backendUrl)}/api/mills`)
      .then((response) => {
        if (!response.ok) throw new Error(`Mill list request failed (${response.status})`);
        return response.json();
      })
      .then((result) => {
        if (!active) return;
        if (!Array.isArray(result)) throw new Error('Mill list response is invalid');
        setMills(result);
        setSelectedMill((current) => current || result[0] || '');
        setMillLoadError('');
      })
      .catch((error) => { if (active) setMillLoadError(error.message || 'Mill inventory unavailable.'); });
    return () => { active = false; };
  }, [backendUrl]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#overview" aria-label="LafargeHolcim home">
          <span className="brand-mark"><img src={logo} alt="" /></span>
          <span>LAFARGEHOLCIM <span className="brand-divider">/</span> CÔTE D'IVOIRE</span>
        </a>
        <nav className="primary-nav" aria-label="Plant views">
          <button className={activePage === 'overview' ? 'primary-nav-active' : ''} type="button" onClick={() => setActivePage('overview')}><Activity size={15} /> System Overview</button>
          <button className={activePage === 'mill-monitor' ? 'primary-nav-active' : ''} type="button" aria-busy={!mills.length && !millLoadError} onClick={() => setActivePage('mill-monitor')}><Factory size={15} /> Individual Mill Monitor</button>
        </nav>
        <div className="topbar-meta"><span className="system-dot" /> PREDICTIVE MAINTENANCE</div>
      </header>
      {millLoadError && <div className="monitor-error" role="alert">{millLoadError}</div>}
      {activePage === 'overview'
        ? <PlantOverview mills={mills} backendUrl={backendUrl} onOpenMill={(mill) => { setSelectedMill(mill); setActivePage('mill-monitor'); }} />
        : <IndividualMillMonitor mills={mills} backendUrl={backendUrl} initialMill={selectedMill} />}
    </main>
  );
}
