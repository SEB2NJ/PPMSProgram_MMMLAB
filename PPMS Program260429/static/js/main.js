// Request notification permission
if (window.Notification && Notification.permission !== "granted") {
    Notification.requestPermission();
}

const socket = io();

// UI Elements
const tempVal = document.getElementById('temp-val');
const fieldVal = document.getElementById('field-val');
const posVal = document.getElementById('pos-val');
const ampVal = document.getElementById('amp-val');
const freqVal = document.getElementById('freq-val');
const heVal = document.getElementById('he-val');
const logContainer = document.getElementById('log-container');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const addBtn = document.getElementById('add-btn');
const clearBtn = document.getElementById('clear-btn');
const queueBody = document.getElementById('queue-body');
const modal = document.getElementById('control-modal');
const ctx = document.getElementById('dataChart').getContext('2d');

let activeProperty = null;
let lastStatus = null;

// Initialize Chart
let dataChart = new Chart(ctx, {
    type: 'scatter',
    data: {
        datasets: [{
            label: 'Measurement Data',
            data: [],
            backgroundColor: 'rgba(52, 152, 219, 0.8)',
            borderColor: 'rgba(52, 152, 219, 1)',
            borderWidth: 1,
            showLine: true,
            tension: 0.1
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            x: { 
                title: { display: true, text: 'Time' },
                grid: { color: '#eee' }
            },
            y: { 
                title: { display: true, text: 'Signal' },
                grid: { color: '#eee' }
            }
        },
        plugins: {
            legend: { display: false }
        }
    }
});

const xAxisSelect = document.getElementById('plot-x-axis');
xAxisSelect.addEventListener('change', (e) => {
    dataChart.options.scales.x.title.text = e.target.value;
    dataChart.update();
});

document.getElementById('clear-plot').addEventListener('click', () => {
    dataChart.data.datasets[0].data = [];
    dataChart.update();
});

// Modal Controls
window.openControl = function(prop) {
    activeProperty = prop;
    document.getElementById('modal-title').innerText = `Set ${prop.toUpperCase()}`;
    
    // Hide all forms
    document.querySelectorAll('.control-form').forEach(f => f.style.display = 'none');
    
    // Show active form and pre-fill values
    const form = document.getElementById(`form-${prop}`);
    if (form) {
        form.style.display = 'block';
        if (lastStatus) {
            if (prop === 'temp') document.getElementById('set-temp-target').value = lastStatus.temp.toFixed(2);
            else if (prop === 'field') document.getElementById('set-field-target').value = lastStatus.field.toFixed(0);
            else if (prop === 'pos') document.getElementById('set-pos-target').value = lastStatus.pos.toFixed(2);
            else if (prop === 'amp') {
                document.getElementById('set-amp-target').value = lastStatus.amp.toFixed(3);
                document.getElementById('set-amp-freq').value = lastStatus.freq.toFixed(2);
            }
        }
    }
    
    modal.style.display = 'block';
};

window.closeControl = function() {
    modal.style.display = 'none';
};

window.submitControl = function() {
    let params = {};
    if (activeProperty === 'temp') {
        params = {
            target: parseFloat(document.getElementById('set-temp-target').value),
            rate: parseFloat(document.getElementById('set-temp-rate').value),
            waittime: parseFloat(document.getElementById('set-temp-wait').value)
        };
    } else if (activeProperty === 'field') {
        params = {
            target: parseFloat(document.getElementById('set-field-target').value),
            approach: parseInt(document.getElementById('set-field-approach').value),
            mode: parseInt(document.getElementById('set-field-mode').value),
            waittime: parseFloat(document.getElementById('set-field-wait').value)
        };
    } else if (activeProperty === 'pos') {
        params = {
            target: parseFloat(document.getElementById('set-pos-target').value)
        };
    } else if (activeProperty === 'amp') {
        params = {
            target: parseFloat(document.getElementById('set-amp-target').value),
            freq: parseFloat(document.getElementById('set-amp-freq').value),
            offset: parseFloat(document.getElementById('set-amp-offset').value),
            waittime: parseFloat(document.getElementById('set-amp-wait').value)
        };
    }

    fetch('/set_property', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ property: activeProperty, params: params })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            addLog(`System: Manual ${activeProperty} set command sent.`);
            closeControl();
        } else {
            alert(data.message);
        }
    });
};

// Close modal when clicking outside
window.onclick = function(event) {
    if (event.target == modal) {
        closeControl();
    }
};

const seqPathInput = document.getElementById('seq-path');
const saveDirInput = document.getElementById('save-dir');
const fileNameInput = document.getElementById('file-name');
const browseSeqBtn = document.getElementById('browse-seq');
const browseSaveBtn = document.getElementById('browse-save');

let selectedPaths = [];

// File Selection Handlers
browseSeqBtn.addEventListener('click', () => {
    fetch('/select_file')
    .then(response => response.json())
    .then(data => {
        if (data.paths && data.paths.length > 0) {
            selectedPaths = data.paths;
            if (selectedPaths.length === 1) {
                seqPathInput.value = selectedPaths[0];
            } else {
                seqPathInput.value = `${selectedPaths.length} files selected`;
            }
        }
    });
});

browseSaveBtn.addEventListener('click', () => {
    fetch('/select_directory')
    .then(response => response.json())
    .then(data => {
        if (data.path) {
            saveDirInput.value = data.path;
        }
    });
});

// Socket Events
socket.on('connect', () => {
    document.getElementById('connection-status').style.color = '#27ae60';
    document.getElementById('connection-status').innerText = '● Connected';
    addLog('System: WebSocket connected.');
});

socket.on('disconnect', () => {
    document.getElementById('connection-status').style.color = '#c0392b';
    document.getElementById('connection-status').innerText = '○ Disconnected';
    addLog('System: WebSocket disconnected.');
});

socket.on('status_update', (data) => {
    lastStatus = data;
    tempVal.innerText = `${data.temp.toFixed(2)} K`;
    fieldVal.innerText = `${data.field.toFixed(2)} Oe`;
    posVal.innerText = `${data.pos.toFixed(2)} deg`;
    ampVal.innerText = `${data.amp.toFixed(3)} mA`;
    freqVal.innerText = `${data.freq.toFixed(2)} Hz`;
    
    // Update current command
    const cmdEl = document.getElementById('current-command');
    if (cmdEl && data.currentCommand) {
        cmdEl.innerText = `System: ${data.currentCommand}`;
        
        // Highlight current step in sequence panel
        const match = data.currentCommand.match(/\((\d+)\/\d+\)/);
        if (match) {
            const stepIdx = parseInt(match[1]) - 1;
            highlightStep(stepIdx);
        }
    }
    
    // He Level update with Gauge
    const hePercent = data.heLevel;
    heVal.innerText = `${hePercent.toFixed(1)} %`;
    const heBar = document.getElementById('he-bar');
    if (heBar) {
        heBar.style.height = `${hePercent}%`;
        // Color logic: Red if below 60%, Blue otherwise
        if (hePercent < 60) {
            heBar.style.backgroundColor = '#e74c3c'; // Red
        } else {
            heBar.style.backgroundColor = '#3498db'; // Blue
        }
    }
});

socket.on('sequence_data', (data) => {
    const panel = document.getElementById('sequence-panel');
    const nameEl = document.getElementById('current-seq-name');
    const stepsEl = document.getElementById('sequence-steps');
    
    // Update active task detail
    const detailPanel = document.getElementById('active-task-detail');
    const activeName = document.getElementById('active-task-name');
    const activePath = document.getElementById('active-task-path');
    if (detailPanel) {
        detailPanel.style.display = 'block';
        activeName.innerText = data.fileName;
        activePath.innerText = `File: ${data.fileName}`; 
    }

    panel.style.display = 'block';
    nameEl.innerText = data.fileName;
    stepsEl.innerHTML = '';
    
    data.commands.forEach((cmd, idx) => {
        const div = document.createElement('div');
        div.id = `step-${idx}`;
        div.style.padding = '3px 5px';
        div.style.borderBottom = '1px solid #eee';
        
        const args = Object.entries(cmd)
            .filter(([k]) => k !== 'command')
            .map(([k, v]) => `${k}: ${v}`)
            .join(', ');
            
        div.innerText = `${idx + 1}. ${cmd.command} [${args}]`;
        stepsEl.appendChild(div);
    });
});

socket.on('log_update', (data) => {
    addLog(data.log);
});

socket.on('measurement_finished', (data) => {
    addLog('System: Queue processing finished.');
    startBtn.disabled = false;
    document.getElementById('sequence-panel').style.display = 'none';
    
    const detailPanel = document.getElementById('active-task-detail');
    if (detailPanel) detailPanel.style.display = 'none';
    
    // Browser notification
    if (window.Notification && Notification.permission === "granted") {
        new Notification("PPMS Measurement Finished", {
            body: "The entire measurement queue has been completed successfully."
        });
    }
});

socket.on('queue_update', (queue) => {
    updateQueueUI(queue);
    updateGlobalProgress(queue);
});

function updateGlobalProgress(queue) {
    const total = queue.length;
    if (total === 0) {
        const progContainer = document.getElementById('queue-progress-container');
        if (progContainer) progContainer.style.display = 'none';
        return;
    }
    
    const completed = queue.filter(t => t.status === 'completed' || t.status === 'error').length;
    const isRunning = queue.some(t => t.status === 'running');
    
    const progContainer = document.getElementById('queue-progress-container');
    const progBar = document.getElementById('queue-progress-bar');
    
    if (progContainer && progBar) {
        if (isRunning || (completed > 0 && completed < total)) {
            progContainer.style.display = 'block';
            const percent = (completed / total) * 100;
            progBar.style.width = `${percent}%`;
        } else {
            progContainer.style.display = 'none';
        }
    }
}

document.getElementById('snapshot-plot').addEventListener('click', () => {
    const link = document.createElement('a');
    link.download = `ppms_plot_${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.png`;
    link.href = document.getElementById('dataChart').toDataURL('image/png');
    link.click();
});

socket.on('new_data_point', (point) => {
    const xKey = xAxisSelect.value;
    const yKey = document.getElementById('plot-y-axis').value;
    
    // Dynamically update Y-axis options if new keys appear
    updateYAxisOptions(point);
    
    let yVal;
    if (yKey === 'Signal') {
        // Auto-detect signal key
        let signalKey = Object.keys(point).find(k => k.endsWith('_R'));
        if (!signalKey) signalKey = Object.keys(point).find(k => k.includes('Signal') || k.includes('Value'));
        if (!signalKey) signalKey = Object.keys(point)[0];
        yVal = point[signalKey];
        dataChart.options.scales.y.title.text = signalKey;
    } else {
        yVal = point[yKey];
        dataChart.options.scales.y.title.text = yKey;
    }
    
    // Update Plot
    dataChart.data.datasets[0].data.push({
        x: point[xKey],
        y: yVal
    });
    
    if (dataChart.data.datasets[0].data.length > 200) {
        dataChart.data.datasets[0].data.shift();
    }
    dataChart.update('none');

    // Update Data Table
    updateDataTable(point);
});

function updateYAxisOptions(point) {
    const ySelect = document.getElementById('plot-y-axis');
    const currentKeys = Array.from(ySelect.options).map(opt => opt.value);
    
    Object.keys(point).forEach(k => {
        if (!currentKeys.includes(k) && typeof point[k] === 'number') {
            const opt = document.createElement('option');
            opt.value = k;
            opt.innerText = k;
            ySelect.appendChild(opt);
        }
    });
}

// Dark Mode Toggle
const darkModeBtn = document.getElementById('dark-mode-toggle');
if (localStorage.getItem('darkMode') === 'enabled') {
    document.body.classList.add('dark-mode');
    darkModeBtn.innerText = '☀️ Light Mode';
}

darkModeBtn.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    if (document.body.classList.contains('dark-mode')) {
        localStorage.setItem('darkMode', 'enabled');
        darkModeBtn.innerText = '☀️ Light Mode';
    } else {
        localStorage.setItem('darkMode', 'disabled');
        darkModeBtn.innerText = '🌙 Dark Mode';
    }
});

// CSV Export
document.getElementById('export-csv-btn').addEventListener('click', () => {
    const head = document.getElementById('data-table-head');
    const body = document.getElementById('data-table-body');
    
    if (body.children.length === 0) {
        alert("No data to export.");
        return;
    }

    let csv = [];
    // Headers
    const headers = Array.from(head.querySelectorAll('th')).map(th => th.innerText);
    csv.push(headers.join(','));
    
    // Rows
    Array.from(body.querySelectorAll('tr')).forEach(tr => {
        const row = Array.from(tr.querySelectorAll('td')).map(td => td.innerText);
        csv.push(row.join(','));
    });

    const blob = new Blob([csv.join('\n')], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ppms_data_export_${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
});

// Helper Functions
function updateDataTable(point) {
    const head = document.getElementById('data-table-head');
    const body = document.getElementById('data-table-body');
    
    // Initialize headers if empty
    if (head.children.length === 0) {
        const tr = document.createElement('tr');
        Object.keys(point).forEach(k => {
            const th = document.createElement('th');
            th.innerText = k;
            tr.appendChild(th);
        });
        head.appendChild(tr);
    }
    
    // Add row
    const tr = document.createElement('tr');
    Object.values(point).forEach(v => {
        const td = document.createElement('td');
        td.innerText = typeof v === 'number' ? v.toFixed(6) : v;
        tr.appendChild(td);
    });
    
    body.insertBefore(tr, body.firstChild);
    
    // Keep only last 10 rows
    if (body.children.length > 10) {
        body.removeChild(body.lastChild);
    }
}

document.getElementById('open-folder-btn').addEventListener('click', () => {
    const path = saveDirInput.value;
    if (!path) {
        alert("Please specify a data save directory first.");
        return;
    }
    fetch('/open_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: path })
    });
});

document.getElementById('download-log').addEventListener('click', () => {
    const logs = Array.from(document.querySelectorAll('.log-entry')).map(e => e.innerText).join('\n');
    const blob = new Blob([logs], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ppms_session_log_${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.txt`;
    a.click();
    window.URL.revokeObjectURL(url);
});

function highlightStep(idx) {
    const stepsEl = document.getElementById('sequence-steps');
    if (!stepsEl) return;
    const steps = stepsEl.children;
    for (let i = 0; i < steps.length; i++) {
        if (i === idx) {
            steps[i].style.backgroundColor = '#e1f5fe';
            steps[i].style.fontWeight = 'bold';
            steps[i].style.color = '#0277bd';
            steps[i].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
            steps[i].style.backgroundColor = 'transparent';
            steps[i].style.fontWeight = 'normal';
            steps[i].style.color = 'inherit';
        }
    }
}

function addLog(message) {
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerText = message;
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

function updateQueueUI(queue) {
    queueBody.innerHTML = '';
    queue.forEach(task => {
        const row = document.createElement('tr');
        row.setAttribute('data-id', task.id);
        
        const deleteBtn = task.status === 'waiting' ? 
            `<button class="btn-delete" onclick="deleteTask(${task.id})">&times;</button>` : '';
        
        const dragHandle = task.status === 'waiting' ? 
            `<span class="handle">&#9776;</span>` : '';
        
        row.innerHTML = `
            <td>${dragHandle}</td>
            <td>${task.dataSaveFileName}</td>
            <td style="font-size: 0.8em; color: #666;">${task.sequenceDirectory}</td>
            <td><span class="status-${task.status}">${task.status.toUpperCase()}</span></td>
            <td style="text-align: right;">${deleteBtn}</td>
        `;
        queueBody.appendChild(row);
    });
}

// Initialize Sortable
if (typeof Sortable !== 'undefined') {
    new Sortable(queueBody, {
        handle: '.handle',
        animation: 150,
        ghostClass: 'sortable-ghost',
        onEnd: function() {
            const rows = queueBody.querySelectorAll('tr');
            const newOrder = Array.from(rows).map(row => parseInt(row.getAttribute('data-id')));
            
            fetch('/reorder_queue', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ order: newOrder })
            });
        }
    });
}

function deleteTask(taskId) {
    fetch('/delete_from_queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: taskId })
    });
}

// Control Events
addBtn.addEventListener('click', () => {
    let sequenceInput = seqPathInput.value;
    
    if (selectedPaths.length > 1 && sequenceInput.includes('files selected')) {
        sequenceInput = selectedPaths;
    }

    const settings = {
        sequenceDirectory: sequenceInput,
        dataSaveDirectory: saveDirInput.value,
        dataSaveFileName: fileNameInput.value
    };

    if (!settings.sequenceDirectory || (Array.isArray(settings.sequenceDirectory) && settings.sequenceDirectory.length === 0)) {
        alert("Please provide a sequence file path.");
        return;
    }

    fetch('/add_to_queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            const taskLabel = Array.isArray(sequenceInput) ? `${sequenceInput.length} tasks` : settings.dataSaveFileName || "New task";
            addLog(`System: ${taskLabel} added to queue.`);
            selectedPaths = [];
            if (Array.isArray(sequenceInput)) seqPathInput.value = "";
            fileNameInput.value = ""; 
        } else {
            addLog(`Error: ${data.message}`);
        }
    });
});

startBtn.addEventListener('click', () => {
    fetch('/start', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            addLog('System: Queue execution started.');
            startBtn.disabled = true;
        } else {
            alert(data.message);
        }
    });
});

stopBtn.addEventListener('click', () => {
    fetch('/stop', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            addLog('System: Stop/Abort signal sent.');
        }
    });
});

clearBtn.addEventListener('click', () => {
    fetch('/clear_queue', {
        method: 'POST'
    });
});
