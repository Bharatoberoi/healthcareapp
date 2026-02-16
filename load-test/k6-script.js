import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  vus: 10,
  duration: '30s',
  thresholds: {
    http_req_duration: ['p(95)<50']
  }
};

export default function () {
  const base = __ENV.TARGET || 'http://127.0.0.1';
  const res = http.get(`${base}/health`);
  check(res, { 'status was 200': (r) => r.status === 200 });
  sleep(1);
}
