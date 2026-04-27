// Shared WebSocket utilities for MCV Milling Vision System

class StatusMonitor {
    constructor() {
        this.ws = null;
        this.onStatus = null;
    }

    connect() {
        if (this.ws) return;
        this.ws = new WebSocket(`ws://${window.location.host}/ws/status/`);
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'status') {
                this._updateUI(data);
                if (this.onStatus) this.onStatus(data);
            }
        };
        this.ws.onclose = () => {
            this.ws = null;
            setTimeout(() => this.connect(), 3000);
        };
    }

    _updateUI(data) {
        const indicator = document.getElementById('robot-indicator');
        const statusText = document.getElementById('robot-status-text');
        const topbar = document.getElementById('topbar-connection');

        if (data.connected) {
            if (indicator) indicator.className = 'status-dot bg-success';
            if (statusText) statusText.textContent = 'Connected';
            if (topbar) { topbar.className = 'badge bg-success'; topbar.textContent = 'Connected'; }
            if (data.info && data.info.name) {
                const robotName = document.getElementById('robot-name');
                if (robotName) robotName.textContent = data.info.name;
            }
        } else {
            if (indicator) indicator.className = 'status-dot bg-danger';
            if (statusText) statusText.textContent = 'Disconnected';
            if (topbar) { topbar.className = 'badge bg-danger'; topbar.textContent = 'Disconnected'; }
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// Auto-start status monitor on page load
document.addEventListener('DOMContentLoaded', () => {
    const monitor = new StatusMonitor();
    monitor.connect();
});
