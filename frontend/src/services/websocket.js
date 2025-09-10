import { authService } from './auth';

const clientId = crypto.randomUUID(); // generate unique client ID

function buildWsUrl(token) {
  // In development, use the Vite proxy
  const baseDev = `/ws/${clientId}`;
  // In production, use the configured URL or fallback
  const baseProd = (import.meta.env.VITE_WS_URL || `/ws/${clientId}`);
  const base = import.meta.env.DEV ? baseDev : baseProd;
  const sep = base.includes('?') ? '&' : '?';
  return token ? `${base}${sep}token=${encodeURIComponent(token)}` : base;
}

class WebSocketService {
  constructor() {
    this.ws = null;
    this.listeners = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.isConnecting = false;
    this.pingInterval = null;
    this.pongTimeout = null;
    this.pingIntervalMs = 30000; // 30s
    this.pongTimeoutMs = 5000; // 5s
  }

  connect() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;
    if (this.isConnecting) return;

    this.isConnecting = true;
    try {
      const token = authService.getToken();
      const url = buildWsUrl(token);
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log("✅ WebSocket connected:", this.ws.url);
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.startHeartbeat();
        this.emit("connection", { status: "connected" });
      };

      this.ws.onmessage = (event) => {
        if (event.data === "ping") {
          this.ws.send("pong");
          return;
        }
        if (event.data === "pong") {
          this.handlePong();
          return;
        }
        try {
          const data = JSON.parse(event.data);
          this.emit(data.type || "message", data.data || data);
        } catch {
          this.emit("message", event.data);
        }
      };

      this.ws.onclose = async () => {
        console.log("❌ WebSocket disconnected");
        this.isConnecting = false;
        this.stopHeartbeat();
        this.emit("connection", { status: "disconnected" });
        // Attempt to refresh token (auto-login) before reconnect
        try { await authService.ensureLoggedIn(); } catch {}
        this.scheduleReconnect();
      };

      this.ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        this.isConnecting = false;
        this.emit("connection", { status: "error", error });
      };
    } catch (error) {
      console.error("Failed to connect WebSocket:", error);
      this.isConnecting = false;
      this.scheduleReconnect();
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.stopHeartbeat();
    this.listeners.clear();
  }

  startHeartbeat() {
    this.stopHeartbeat();
    this.pingInterval = setInterval(() => this.sendPing(), this.pingIntervalMs);
  }

  stopHeartbeat() {
    if (this.pingInterval) clearInterval(this.pingInterval);
    if (this.pongTimeout) clearTimeout(this.pongTimeout);
    this.pingInterval = null;
    this.pongTimeout = null;
  }

  sendPing() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.pongTimeout = setTimeout(() => {
        console.log("⚠️ Pong timeout - closing connection");
        this.ws.close();
        this.emit("connection", { status: "timeout" });
      }, this.pongTimeoutMs);

      try {
        this.ws.send("ping");
      } catch {
        this.ws.close();
      }
    }
  }

  handlePong() {
    if (this.pongTimeout) {
      clearTimeout(this.pongTimeout);
      this.pongTimeout = null;
      console.log("✅ Pong received - healthy");
    }
  }

  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log("🚫 Max reconnection attempts reached");
      return;
    }
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * 2 ** (this.reconnectAttempts - 1);
    setTimeout(() => {
      console.log(`🔄 Reconnecting (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
      this.connect();
    }, delay);
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn("WebSocket not open. Cannot send:", data);
    }
  }

  on(event, callback) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event).add(callback);
  }

  off(event, callback) {
    if (this.listeners.has(event)) this.listeners.get(event).delete(callback);
  }

  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(cb => {
        try { cb(data); } catch (err) { console.error("Handler error:", err); }
      });
    }
  }

  getStatus() {
    if (!this.ws) return "disconnected";
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING: return "connecting";
      case WebSocket.OPEN: return "connected";
      case WebSocket.CLOSING: return "disconnecting";
      case WebSocket.CLOSED: return "disconnected";
      default: return "unknown";
    }
  }
}

export const wsService = new WebSocketService();
export default wsService;
