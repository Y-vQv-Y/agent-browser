// AgentBrowser Web GUI

let ws = null;
let isRunning = false;

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
        addLog('Connected to AgentBrowser', 'info');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleMessage(data);
    };

    ws.onclose = () => {
        addLog('Disconnected. Reconnecting...', 'error');
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => {
        addLog('Connection error', 'error');
    };
}

function handleMessage(data) {
    switch (data.type) {
        case 'start':
            setStatus('running');
            addLog(`Task started: ${data.task}`, 'info');
            break;
        case 'step':
            const status = data.success ? 'OK' : 'FAIL';
            addLog(`[${status}] ${data.tool} (${data.duration.toFixed(1)}s)`, data.success ? 'step' : 'error');
            break;
        case 'complete':
            isRunning = false;
            document.getElementById('runBtn').disabled = false;
            if (data.success) {
                setStatus('success');
                addLog(`Task completed: ${data.result}`, 'success');
            } else {
                setStatus('error');
                addLog(`Task failed: ${data.result}`, 'error');
            }
            addLog(`Steps: ${data.steps} | Time: ${data.duration.toFixed(1)}s`, 'info');
            break;
        case 'error':
            isRunning = false;
            document.getElementById('runBtn').disabled = false;
            setStatus('error');
            addLog(`Error: ${data.error}`, 'error');
            break;
        case 'screenshot':
            const img = document.getElementById('screenshotImg');
            img.src = `data:image/png;base64,${data.image}`;
            img.style.display = 'block';
            document.getElementById('noScreenshot').style.display = 'none';
            break;
    }
}

function runTask() {
    const taskInput = document.getElementById('taskInput');
    const task = taskInput.value.trim();
    if (!task) return;

    if (!ws || ws.readyState !== WebSocket.OPEN) {
        addLog('Not connected. Trying to reconnect...', 'error');
        connectWebSocket();
        return;
    }

    isRunning = true;
    document.getElementById('runBtn').disabled = true;
    setStatus('running');

    ws.send(JSON.stringify({ action: 'run_task', task: task }));
}

function takeScreenshot() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ action: 'screenshot' }));
    switchTab('screenshot');
}

function showSchedule() {
    document.getElementById('schedulePanel').classList.remove('hidden');
}

function hideSchedule() {
    document.getElementById('schedulePanel').classList.add('hidden');
}

async function scheduleTask() {
    const task = document.getElementById('taskInput').value.trim();
    if (!task) return;

    const time = document.getElementById('scheduleTime').value;
    const cron = document.getElementById('scheduleCron').value.trim();
    const preCheck = document.getElementById('preCheck').checked;

    const body = { task, pre_check: preCheck };
    if (time) body.execute_at = new Date(time).toISOString();
    if (cron) body.cron = cron;

    try {
        const resp = await fetch('/api/schedule', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await resp.json();
        addLog(`Task scheduled: ${data.task_id}`, 'success');
        hideSchedule();
        loadTasks();
    } catch (e) {
        addLog(`Schedule error: ${e.message}`, 'error');
    }
}

async function loadTasks() {
    try {
        const resp = await fetch('/api/tasks');
        const data = await resp.json();
        const tbody = document.getElementById('tasksBody');
        tbody.innerHTML = '';
        for (const task of data.tasks) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${task.task_id}</td>
                <td>${task.description.substring(0, 60)}</td>
                <td>${task.status}</td>
                <td>${task.execute_at || task.cron || ''}</td>
            `;
            tbody.appendChild(tr);
        }
    } catch (e) {
        console.error('Failed to load tasks:', e);
    }
}

function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));

    event.target.classList.add('active');
    document.getElementById(`${tabName}Panel`).classList.add('active');

    if (tabName === 'tasks') loadTasks();
}

function setStatus(status) {
    const el = document.getElementById('status');
    el.className = `status ${status}`;
    el.textContent = status.charAt(0).toUpperCase() + status.slice(1);
}

function addLog(message, type = 'info') {
    const output = document.getElementById('logOutput');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const time = new Date().toLocaleTimeString();
    entry.textContent = `[${time}] ${message}`;
    output.appendChild(entry);
    output.scrollTop = output.scrollHeight;
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();

    // Ctrl+Enter to run
    document.getElementById('taskInput').addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            runTask();
        }
    });
});
