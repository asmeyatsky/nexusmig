/* Nexus Migration Accelerator — Web UI */

const state = {
  currentStep: 0,
  inputMode: 'csv',
  outputMode: 'file',
  objects: ['accounts', 'contacts', 'opportunities', 'activities'],
  csvPaths: {},
  sessionId: null,
  runId: null,
  dryRun: false,
};

/* ── Tab navigation ── */
function switchTab(tabName) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
  document.getElementById(`panel-${tabName}`).classList.add('active');
}

/* ── Wizard navigation ── */
function goToStep(step) {
  const steps = document.querySelectorAll('.wizard-step');
  const panels = document.querySelectorAll('.step-panel');

  steps.forEach((s, i) => {
    s.classList.remove('active', 'done');
    if (i < step) s.classList.add('done');
    if (i === step) s.classList.add('active');
  });

  panels.forEach(p => p.classList.remove('active'));
  panels[step].classList.add('active');
  state.currentStep = step;
}

function nextStep() {
  if (validateCurrentStep()) {
    goToStep(state.currentStep + 1);
    if (state.currentStep === 3) populateReview();
  }
}

function prevStep() {
  if (state.currentStep > 0) goToStep(state.currentStep - 1);
}

/* ── Step 1: Input mode ── */
function setInputMode(mode) {
  state.inputMode = mode;
  document.getElementById('sf-api-fields').style.display = mode === 'api' ? 'block' : 'none';
  document.getElementById('csv-upload-fields').style.display = mode === 'csv' ? 'block' : 'none';
  document.querySelectorAll('[name="input_mode"]').forEach(r => r.checked = r.value === mode);
}

/* ── CSV Upload ── */
async function uploadFile(objectType, input) {
  const file = input.files[0];
  if (!file) return;

  const zone = input.closest('.upload-zone') || input.parentElement;
  const label = zone.querySelector('.upload-label');

  const formData = new FormData();
  formData.append(objectType, file);

  try {
    const resp = await fetch('/api/upload-csv', { method: 'POST', body: formData });
    const data = await resp.json();
    state.sessionId = data.session_id;
    Object.assign(state.csvPaths, data.paths);

    zone.classList.add('has-file');
    if (label) label.textContent = `${file.name} uploaded`;
  } catch (e) {
    alert(`Upload failed: ${e.message}`);
  }
}

/* ── Step 2: Objects ── */
function toggleObject(obj) {
  const idx = state.objects.indexOf(obj);
  if (idx >= 0) state.objects.splice(idx, 1);
  else state.objects.push(obj);
}

/* ── Step 3: Output ── */
function setOutputMode(mode) {
  state.outputMode = mode;
  document.getElementById('nexus-api-fields').style.display =
    (mode === 'api' || mode === 'both') ? 'block' : 'none';
}

/* ── Step 4: Review ── */
function populateReview() {
  const el = document.getElementById('review-content');
  const rows = [
    ['Input Mode', state.inputMode.toUpperCase()],
    ['Output Mode', state.outputMode.toUpperCase()],
    ['Objects', state.objects.join(', ')],
    ['Duplicate Strategy', document.getElementById('dup-strategy')?.value || 'skip'],
  ];
  if (state.inputMode === 'csv') {
    rows.push(['CSV Files', Object.keys(state.csvPaths).join(', ') || 'None uploaded']);
  }
  if (state.inputMode === 'api') {
    rows.push(['SF Username', document.getElementById('sf-username')?.value || '']);
  }
  if (state.outputMode !== 'file') {
    rows.push(['Nexus URL', document.getElementById('nexus-url')?.value || '']);
  }

  el.innerHTML = rows.map(([l, v]) =>
    `<div class="review-row"><span class="label">${l}</span><span class="value">${v}</span></div>`
  ).join('');
}

/* ── Validation ── */
function validateCurrentStep() {
  if (state.currentStep === 0 && state.inputMode === 'csv') {
    if (Object.keys(state.csvPaths).length === 0) {
      alert('Please upload at least one CSV file.');
      return false;
    }
  }
  if (state.currentStep === 0 && state.inputMode === 'api') {
    if (!document.getElementById('sf-username')?.value) {
      alert('Please enter Salesforce credentials.');
      return false;
    }
  }
  if (state.currentStep === 1 && state.objects.length === 0) {
    alert('Please select at least one object type.');
    return false;
  }
  return true;
}

/* ── Run migration ── */
async function startMigration(dryRun) {
  state.dryRun = dryRun;
  goToStep(4);

  const config = buildConfig();
  config.dry_run = dryRun;

  try {
    const resp = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    const data = await resp.json();
    state.runId = data.run_id;
    streamProgress(data.run_id);
  } catch (e) {
    logProgress('error', `Failed to start: ${e.message}`);
  }
}

function buildConfig() {
  const config = {
    input_mode: state.inputMode,
    output_mode: state.outputMode,
    objects: state.objects,
    csv_paths: state.csvPaths,
    duplicate_strategy: document.getElementById('dup-strategy')?.value || 'skip',
    field_overrides: {},
    stage_overrides: {},
  };

  if (state.inputMode === 'api') {
    config.salesforce = {
      username: document.getElementById('sf-username')?.value || '',
      password: document.getElementById('sf-password')?.value || '',
      security_token: document.getElementById('sf-token')?.value || '',
      domain: document.getElementById('sf-domain')?.value || 'login',
    };
  }

  if (state.outputMode !== 'file') {
    config.nexus_api = {
      base_url: document.getElementById('nexus-url')?.value || '',
      api_key: document.getElementById('nexus-key')?.value || '',
      batch_size: parseInt(document.getElementById('nexus-batch')?.value || '50'),
    };
  }

  return config;
}

/* ── SSE Progress ── */
function streamProgress(runId) {
  const log = document.getElementById('progress-log');
  const bar = document.getElementById('progress-bar');
  const status = document.getElementById('progress-status');
  let completed = 0;
  const totalObjects = state.objects.length;

  const source = new EventSource(`/api/progress/${runId}`);

  source.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.phase === 'done') {
      source.close();
      bar.style.width = '100%';
      status.textContent = 'Migration complete';
      loadResult(runId);
      return;
    }

    if (data.phase === 'complete') {
      completed++;
      bar.style.width = `${Math.round((completed / totalObjects) * 100)}%`;
    }

    status.textContent = data.message || `${data.phase} ${data.object_type}`;
    logProgress(data.phase, `[${data.object_type}] ${data.message}`);
  };

  source.onerror = () => {
    source.close();
    logProgress('error', 'Connection lost — check server logs');
  };
}

function logProgress(phase, message) {
  const log = document.getElementById('progress-log');
  const line = document.createElement('div');
  line.className = `line phase-${phase}`;
  line.textContent = message;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}

/* ── Results ── */
async function loadResult(runId) {
  try {
    const resp = await fetch(`/api/result/${runId}`);
    if (!resp.ok) return;
    const data = await resp.json();

    document.getElementById('result-section').style.display = 'block';
    document.getElementById('stat-extracted').textContent = data.total_extracted;
    document.getElementById('stat-loaded').textContent = data.total_loaded;
    document.getElementById('stat-quarantined').textContent = data.total_quarantined;
    document.getElementById('stat-duration').textContent = `${data.duration_seconds.toFixed(1)}s`;

    const qCard = document.getElementById('stat-quarantined').closest('.stat-card');
    if (data.total_quarantined > 0) qCard.classList.add('warning');
    else qCard.classList.add('success');

    document.getElementById('result-actions').style.display = 'flex';
    document.getElementById('btn-view-report').onclick = () =>
      window.open(`/api/report/${runId}`, '_blank');
  } catch (e) { /* ignore */ }
}

/* ── History ── */
async function loadHistory() {
  try {
    const resp = await fetch('/api/history');
    const runs = await resp.json();
    const tbody = document.getElementById('history-body');
    tbody.innerHTML = '';

    if (runs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--gray-600)">No migration runs yet</td></tr>';
      return;
    }

    runs.forEach(r => {
      const ts = r.timestamp.substring(0, 19).replace('T', ' ');
      const badge = r.dry_run ? '<span class="badge badge-dry">DRY</span>' :
        (r.success ? '<span class="badge badge-ok">OK</span>' : '<span class="badge badge-warn">WARN</span>');
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${ts}</td>
        <td>${r.input_mode || '-'}</td>
        <td>${r.total_extracted}</td>
        <td>${r.total_loaded}</td>
        <td>${r.total_quarantined}</td>
        <td>${r.duration_seconds.toFixed(1)}s</td>
        <td>${badge}
          <button class="btn btn-secondary" style="padding:0.2rem 0.5rem;font-size:0.75rem;margin-left:0.5rem"
                  onclick="window.open('/api/report/${r.run_id}','_blank')">Report</button>
        </td>`;
      tbody.appendChild(row);
    });
  } catch (e) { /* ignore */ }
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  goToStep(0);
  setInputMode('csv');
  setOutputMode('file');
  loadHistory();

  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });
});
