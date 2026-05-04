import { useState } from 'react';

export default function Home() {
  const [query, setQuery] = useState('I need a chiropractor visit for back pain');
  const [location, setLocation] = useState('90210');
  const [network, setNetwork] = useState('Aetna');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch('/api/run-workflow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, user_location: location, insurance_network: network }),
      });
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setResult({ success: false, error: String(e) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: '40px auto', fontFamily: 'Arial, sans-serif' }}>
      <h1>LangGraph Medical Cost UI</h1>
      <div style={{ marginBottom: 12 }}>
        <label>Query:</label><br />
        <input value={query} onChange={(e) => setQuery(e.target.value)} style={{ width: '100%', padding: 8 }} />
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <label>Location:</label><br />
          <input value={location} onChange={(e) => setLocation(e.target.value)} style={{ width: '100%', padding: 8 }} />
        </div>
        <div style={{ flex: 1 }}>
          <label>Insurance Network:</label><br />
          <input value={network} onChange={(e) => setNetwork(e.target.value)} style={{ width: '100%', padding: 8 }} />
        </div>
      </div>
      <div>
        <button onClick={run} disabled={loading} style={{ padding: '10px 16px' }}>
          {loading ? 'Running...' : 'Run Workflow'}
        </button>
      </div>

      <div style={{ marginTop: 20 }}>
        <h3>Result</h3>
        <pre style={{ background: '#f6f8fa', padding: 12, minHeight: 120 }}>{result ? JSON.stringify(result, null, 2) : 'No result yet'}</pre>
      </div>
    </div>
  );
}

