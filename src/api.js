const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001';

async function request(path) {
  const response = await fetch(`${API_BASE}${path}`, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `DarkLens API returned ${response.status}`);
  }
  return response.json();
}

export const getCases = () => request('/api/cases');
export const getCase = (caseId) => request(`/api/cases/${encodeURIComponent(caseId)}`);
export const getTimeline = (caseId) => request(`/api/cases/${encodeURIComponent(caseId)}/timeline`);
export const analyzeCase = (caseId) => request(`/api/cases/${encodeURIComponent(caseId)}/analysis`);
export async function saveAnalysis(caseId) {
  const response = await fetch(`${API_BASE}/api/cases/${encodeURIComponent(caseId)}/analysis`, {
    method: 'POST',
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `DarkLens API returned ${response.status}`);
  }
  return response.json();
}
export const getHealth = () => request('/api/health');
export async function previewCaseBundle(bundle) {
  const response = await fetch(`${API_BASE}/api/cases/preview`, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(bundle),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail.join('\n') : body.detail;
    throw new Error(detail || `DarkLens API returned ${response.status}`);
  }
  return response.json();
}
export async function importCaseBundle(bundle) {
  const response = await fetch(`${API_BASE}/api/cases/import`, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(bundle),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail.join('\n') : body.detail;
    throw new Error(detail || `DarkLens API returned ${response.status}`);
  }
  return response.json();
}
export const reviewLink = (linkId, status, note = '') => fetch(`${API_BASE}/api/links/${encodeURIComponent(linkId)}/review`, {
  method: 'PATCH',
  headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
  body: JSON.stringify({ status, note }),
}).then(async response => {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `DarkLens API returned ${response.status}`);
  }
  return response.json();
});
export const exportCase = (caseId, format = 'json', kind) => format === 'report'
  ? `${API_BASE}/api/cases/${encodeURIComponent(caseId)}/report.md`
  : `${API_BASE}/api/cases/${encodeURIComponent(caseId)}/export.${format}${kind ? `?kind=${encodeURIComponent(kind)}` : ''}`;
