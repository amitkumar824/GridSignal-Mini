import React, { useState, useEffect, useMemo } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export default function App() {
  const [summary, setSummary] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [health, setHealth] = useState(null);
  const [utilityFilter, setUtilityFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [lastAction, setLastAction] = useState(null);
  const [activeTab, setActiveTab] = useState('alerts');

  const fetchData = async () => {
    setLoading(true);
    try {
      const [hRes, sRes, aRes, iRes] = await Promise.all([
        fetch(`${API_BASE}/health`).then(r => r.json()).catch(() => ({ status: 'offline' })),
        fetch(`${API_BASE}/summary`).then(r => r.json()),
        fetch(`${API_BASE}/alerts`).then(r => r.json()),
        fetch(`${API_BASE}/incidents${utilityFilter ? `?utility_type=${utilityFilter}` : ''}`).then(r => r.json()),
      ]);
      setHealth(hRes);
      setSummary(sRes);
      setAlerts(aRes);
      setIncidents(iRes);
    } catch (err) {
      console.error("Failed to fetch dashboard data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [utilityFilter]);

  const handleImport = async (type) => {
    setImporting(true);
    setLastAction(`Importing ${type} dataset...`);
    try {
      const res = await fetch(`${API_BASE}/api/import/${type}`, { method: 'POST' });
      const data = await res.json();
      setLastAction(`Imported ${data.file_processed}: +${data.inserted_new} new, ${data.updated_conflicting} updated, ${data.skipped_identical} identical skipped, ${data.skipped_malformed} malformed skipped.`);
      await fetchData();
    } catch (err) {
      setLastAction(`Import failed: ${err.message}`);
    } finally {
      setImporting(false);
    }
  };

  const filteredIncidents = useMemo(() => {
    return incidents.filter(inc => {
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return (
        inc.incident_id.toLowerCase().includes(q) ||
        (inc.area && inc.area.toLowerCase().includes(q)) ||
        inc.severity.toLowerCase().includes(q) ||
        inc.status.toLowerCase().includes(q)
      );
    });
  }, [incidents, searchQuery]);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      {/* Top Navigation Bar */}
      <header className="bg-slate-900 text-white shadow-md border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-teal-500 flex items-center justify-center text-slate-950 font-black text-xl shadow-inner">
              GS
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold tracking-tight">GridSignal Mini</h1>
                <span className="px-2 py-0.5 rounded text-xs font-semibold bg-teal-900/80 text-teal-300 border border-teal-700">
                  v1.0
                </span>
              </div>
              <p className="text-xs text-slate-400">Utility Incident Intelligence & Cross-Type Pair Correlation</p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap">
            <div className="flex items-center space-x-2 text-xs bg-slate-800/90 px-3 py-1.5 rounded-md border border-slate-700">
              <span className={`inline-block w-2.5 h-2.5 rounded-full ${health?.status === 'ok' ? 'bg-emerald-400 shadow-emerald-400/50 shadow-sm animate-pulse' : 'bg-red-500'}`}></span>
              <span className="text-slate-300">API: {health?.status === 'ok' ? 'Healthy' : 'Connecting...'}</span>
            </div>

            <button 
              onClick={() => handleImport('seed')}
              disabled={importing}
              className="px-3 py-1.5 text-xs font-medium bg-teal-600 hover:bg-teal-500 text-white rounded-md shadow-sm transition-all flex items-center gap-1.5 disabled:opacity-50"
            >
              Run Seed Import
            </button>

            <button 
              onClick={() => handleImport('replay')}
              disabled={importing}
              className="px-3 py-1.5 text-xs font-medium bg-amber-600 hover:bg-amber-500 text-white rounded-md shadow-sm transition-all flex items-center gap-1.5 disabled:opacity-50"
            >
              Run Replay Import
            </button>

            <button 
              onClick={fetchData}
              disabled={loading}
              className="px-3 py-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-md border border-slate-700 transition-all flex items-center gap-1.5"
            >
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>
      </header>

      {lastAction && (
        <div className="bg-teal-950/80 border-b border-teal-800 text-teal-200 text-xs px-4 py-2 flex items-center justify-between">
          <div className="max-w-7xl mx-auto w-full flex items-center justify-between">
            <span>ℹ️ {lastAction}</span>
            <button onClick={() => setLastAction(null)} className="text-teal-400 hover:text-white font-bold ml-4">✕</button>
          </div>
        </div>
      )}

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full flex-1">
        
        {/* Rules & Conflict Policy Callout */}
        <div className="bg-gradient-to-r from-slate-900 to-slate-800 text-slate-300 rounded-xl p-4 shadow-sm border border-slate-700/60 mb-6 flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
          <div className="text-xs space-y-1">
            <div className="font-semibold text-slate-100 flex items-center gap-2">
              🛡️ Correlation Engine Rules & Conflict Policy
            </div>
            <div className="text-slate-400">
              <span className="text-teal-300 font-medium">Correlation:</span> Match GAS ↔ ELECTRIC if Planar Distance ≤ 200 ft <strong>AND</strong> Reporting Time Diff ≤ 6 hours (both inclusive).
            </div>
            <div className="text-slate-400">
              <span className="text-amber-300 font-medium">Conflict Policy:</span> Identical duplicates skipped. Conflicting duplicates update record (Last-Write-Wins). Malformed timestamps skipped with logged warning.
            </div>
          </div>
          <span className="px-2.5 py-1 bg-slate-800 text-slate-200 rounded text-xs border border-slate-700 font-mono">
            Dist: sqrt((x1-x2)² + (y1-y2)²)
          </span>
        </div>

        {/* 4 Summary Stat Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Incidents</span>
            <div className="text-2xl font-bold text-slate-900 mt-1">{summary ? summary.total_incidents : '—'}</div>
            <div className="text-xs text-slate-500 mt-0.5">Stored in SQLite</div>
          </div>

          <div className="bg-white rounded-xl p-4 border border-orange-100 shadow-sm">
            <span className="text-xs font-semibold text-orange-600 uppercase tracking-wider">Gas Incidents</span>
            <div className="text-2xl font-bold text-orange-600 mt-1">{summary ? summary.total_gas : '—'}</div>
            <div className="text-xs text-slate-500 mt-0.5">Utility: GAS</div>
          </div>

          <div className="bg-white rounded-xl p-4 border border-blue-100 shadow-sm">
            <span className="text-xs font-semibold text-blue-600 uppercase tracking-wider">Electric Incidents</span>
            <div className="text-2xl font-bold text-blue-600 mt-1">{summary ? summary.total_electric : '—'}</div>
            <div className="text-xs text-slate-500 mt-0.5">Utility: ELECTRIC</div>
          </div>

          <div className="bg-white rounded-xl p-4 border border-teal-200 shadow-sm ring-1 ring-teal-500/20">
            <span className="text-xs font-semibold text-teal-700 uppercase tracking-wider">Correlated Alerts</span>
            <div className="text-2xl font-bold text-teal-700 mt-1">{summary ? summary.total_alerts : '—'}</div>
            <div className="text-xs text-teal-600 font-medium mt-0.5">Unique Pairs ≤200ft, ≤6hr</div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4 border-b border-slate-200 pb-2">
          <div className="flex space-x-2">
            <button
              onClick={() => setActiveTab('alerts')}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors ${activeTab === 'alerts' ? 'bg-teal-700 text-white shadow-sm' : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'}`}
            >
              Correlated Alerts ({alerts.length})
            </button>

            <button
              onClick={() => setActiveTab('incidents')}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors ${activeTab === 'incidents' ? 'bg-teal-700 text-white shadow-sm' : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'}`}
            >
              All Incidents Inventory ({incidents.length})
            </button>
          </div>

          {activeTab === 'incidents' && (
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Search ID, area, severity..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="px-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 w-48 sm:w-64"
              />

              <select
                value={utilityFilter}
                onChange={(e) => setUtilityFilter(e.target.value)}
                className="text-xs border border-slate-300 rounded-lg px-2.5 py-1.5 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-teal-500"
              >
                <option value="">All Types</option>
                <option value="GAS">Gas Only</option>
                <option value="ELECTRIC">Electric Only</option>
              </select>
            </div>
          )}
        </div>

        {/* TAB 1: Alerts */}
        {activeTab === 'alerts' && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-3.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-slate-800">GAS / ELECTRIC Matched Pairs</h2>
                <p className="text-xs text-slate-500">Planar distance ≤ 200 ft and time difference ≤ 360 min.</p>
              </div>
              <span className="text-xs text-slate-500 font-mono">Sorted by proximity</span>
            </div>

            {alerts.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                <p className="text-sm">No correlated alerts found in database.</p>
                <p className="text-xs text-slate-400 mt-1">Click "Run Seed Import" above to load seed incidents.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-100 text-slate-600 uppercase tracking-wider font-semibold border-b border-slate-200">
                    <tr>
                      <th className="py-3 px-4">#</th>
                      <th className="py-3 px-4">Gas Incident</th>
                      <th className="py-3 px-4">Electric Incident</th>
                      <th className="py-3 px-4">Planar Distance</th>
                      <th className="py-3 px-4">Time Gap</th>
                      <th className="py-3 px-4">Classification</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {alerts.map((alert, idx) => {
                      const isExactBoundaryDist = alert.distance_ft === 200.0;
                      const isExactBoundaryTime = alert.time_gap_minutes === 360.0;
                      return (
                        <tr key={`${alert.gas_incident_id}-${alert.electric_incident_id}`} className="hover:bg-teal-50/40 transition-colors">
                          <td className="py-3.5 px-4 font-mono text-slate-400">{idx + 1}</td>
                          <td className="py-3.5 px-4">
                            <div className="font-bold text-orange-700">🔥 {alert.gas_incident_id}</div>
                            <div className="text-[11px] text-slate-500 mt-0.5">
                              <span className="font-semibold text-slate-600">{alert.gas_severity || '—'}</span> · {alert.gas_status || '—'}
                            </div>
                          </td>
                          <td className="py-3.5 px-4">
                            <div className="font-bold text-blue-700">⚡ {alert.electric_incident_id}</div>
                            <div className="text-[11px] text-slate-500 mt-0.5">
                              <span className="font-semibold text-slate-600">{alert.electric_severity || '—'}</span> · {alert.electric_status || '—'}
                            </div>
                          </td>
                          <td className="py-3.5 px-4 font-mono font-semibold text-slate-900">
                            {alert.distance_ft.toFixed(2)} ft
                          </td>
                          <td className="py-3.5 px-4">
                            <div className="font-semibold text-slate-900 font-mono">
                              {alert.time_gap_minutes.toFixed(1)} min
                            </div>
                            <div className="text-[11px] text-slate-500">
                              {(alert.time_gap_minutes / 60).toFixed(2)} hrs
                            </div>
                          </td>
                          <td className="py-3.5 px-4">
                            {(isExactBoundaryDist || isExactBoundaryTime) ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-purple-100 text-purple-800 border border-purple-200">
                                Exact Limit ({isExactBoundaryDist ? '200 ft' : ''} {isExactBoundaryDist && isExactBoundaryTime ? '&' : ''} {isExactBoundaryTime ? '6 hrs' : ''})
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                ✓ Within Threshold
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: Incidents */}
        {activeTab === 'incidents' && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-3.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-slate-800">Incident Inventory</h2>
                <p className="text-xs text-slate-500">Includes all valid imported records, including those with missing coordinates.</p>
              </div>
              <span className="text-xs text-slate-500">Showing {filteredIncidents.length} of {incidents.length}</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-100 text-slate-600 uppercase tracking-wider font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-4">ID</th>
                    <th className="py-3 px-4">Type</th>
                    <th className="py-3 px-4">Coordinates (x, y)</th>
                    <th className="py-3 px-4">Reported At (UTC)</th>
                    <th className="py-3 px-4">Severity</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Area</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredIncidents.map(inc => {
                    const hasCoords = inc.x_ft !== null && inc.y_ft !== null;
                    const isGas = inc.utility_type === 'GAS';
                    return (
                      <tr key={inc.incident_id} className="hover:bg-slate-50 transition-colors">
                        <td className="py-3 px-4 font-mono font-bold text-slate-900">{inc.incident_id}</td>
                        <td className="py-3 px-4">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold ${isGas ? 'bg-orange-100 text-orange-800' : 'bg-blue-100 text-blue-800'}`}>
                            {isGas ? '🔥 GAS' : '⚡ ELECTRIC'}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono">
                          {hasCoords ? (
                            <span className="text-slate-700">({inc.x_ft}, {inc.y_ft}) ft</span>
                          ) : (
                            <span className="text-[11px] font-medium text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                              Missing Coords (Excluded)
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-600">{inc.reported_at}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            inc.severity === 'CRITICAL' ? 'bg-rose-100 text-rose-800' :
                            inc.severity === 'HIGH' ? 'bg-red-100 text-red-800' :
                            inc.severity === 'MEDIUM' ? 'bg-amber-100 text-amber-800' :
                            'bg-slate-100 text-slate-700'
                          }`}>
                            {inc.severity}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                            inc.status === 'OPEN' ? 'bg-emerald-100 text-emerald-800' :
                            inc.status === 'IN_PROGRESS' ? 'bg-blue-100 text-blue-800' :
                            'bg-slate-100 text-slate-600'
                          }`}>
                            {inc.status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-600">{inc.area || '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      <footer className="bg-white border-t border-slate-200 text-slate-500 text-xs py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div>GridSignal Mini · Internal Utility Incident Intelligence Platform</div>
          <div className="font-mono text-slate-400">FastAPI + SQLite + React</div>
        </div>
      </footer>
    </div>
  );
}
