import { spawn } from 'child_process';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const payload = req.body || {};

  // Spawn python process and pipe JSON via stdin
  const path = require('path');
  const repoRoot = path.resolve(process.cwd(), '..');
  const py = spawn('python', ['langgraph_cli.py'], { cwd: repoRoot });

  let stdout = '';
  let stderr = '';

  py.stdout.on('data', (data) => {
    stdout += data.toString();
  });
  py.stderr.on('data', (data) => {
    stderr += data.toString();
  });

  py.on('close', (code) => {
    if (code !== 0) {
      return res.status(500).json({ success: false, error: stderr || 'Python process failed' });
    }
    try {
      const parsed = JSON.parse(stdout);
      return res.status(200).json(parsed);
    } catch (e) {
      return res.status(500).json({ success: false, error: 'Invalid JSON from Python', raw: stdout, stderr });
    }
  });

  // write payload to stdin
  py.stdin.write(JSON.stringify(payload));
  py.stdin.end();
}

