const TOKEN_KEY = 'threatlens_token';

class AuthService {
  constructor() {
    this.token = this.loadToken();
    this._loginPromise = null;
  }

  loadToken() {
    try {
      const raw = localStorage.getItem(TOKEN_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return parsed?.token?.token || null;
    } catch {
      return null;
    }
  }

  saveToken(tokenObj) {
    try {
      localStorage.setItem(TOKEN_KEY, JSON.stringify({ token: tokenObj }));
      this.token = tokenObj?.token || null;
    } catch {}
  }

  clearToken() {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {}
    this.token = null;
  }

  getToken() {
    return this.token || this.loadToken();
  }

  async ensureLoggedIn() {
    const existing = this.getToken();
    if (existing) return existing;

    if (this._loginPromise) return this._loginPromise;

    const username = import.meta.env.VITE_DEFAULT_USERNAME || 'admin';
    const password = import.meta.env.VITE_DEFAULT_PASSWORD || 'admin123';
    const base = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');

    this._loginPromise = (async () => {
      let attempt = 0;
      const maxAttempts = 3;
      let lastErr;
      while (attempt < maxAttempts) {
        try {
          const res = await fetch(`${base}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, remember_me: true })
          });
          if (res.status === 429) {
            // Backoff on rate limit
            const delayMs = 1000 * (2 ** attempt);
            await new Promise(r => setTimeout(r, delayMs));
            attempt++;
            continue;
          }
          if (!res.ok) throw new Error(`Login failed: ${res.status}`);
          const data = await res.json();
          if (data?.token?.token) {
            this.saveToken(data.token);
            return data.token.token;
          }
          throw new Error('No token in login response');
        } catch (e) {
          lastErr = e;
          attempt++;
          // small delay before retry
          await new Promise(r => setTimeout(r, 500));
        }
      }
      throw lastErr || new Error('Login failed');
    })();

    try {
      return await this._loginPromise;
    } finally {
      this._loginPromise = null;
    }
  }
}

export const authService = new AuthService();
export default authService;


