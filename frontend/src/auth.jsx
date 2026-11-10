import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, getToken, setToken, setUnauthorizedHandler } from './api.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [notice, setNotice] = useState('');

  const clearSession = useCallback((message = '') => {
    setToken(null);
    setUser(null);
    setNotice(message);
  }, []);

  // Any 401 from the API (expired or invalid token) signs the user out.
  useEffect(() => {
    setUnauthorizedHandler(() => clearSession('Your session has expired. Sign in again.'));
  }, [clearSession]);

  // Restore the session from a saved token on first load.
  useEffect(() => {
    let cancelled = false;
    async function restore() {
      if (getToken()) {
        try {
          const me = await api.me();
          if (!cancelled) setUser(me);
        } catch {
          // A 401 is handled by the unauthorized handler; other errors leave the user signed out.
        }
      }
      if (!cancelled) setReady(true);
    }
    restore();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username, password) => {
    const { access_token: token } = await api.login(username, password);
    setToken(token);
    try {
      const me = await api.me();
      setUser(me);
      setNotice('');
      return me;
    } catch (error) {
      setToken(null);
      throw error;
    }
  }, []);

  const logout = useCallback(() => clearSession(''), [clearSession]);

  const refreshUser = useCallback(async () => {
    const me = await api.me();
    setUser(me);
    return me;
  }, []);

  const value = useMemo(
    () => ({ user, ready, notice, login, logout, refreshUser }),
    [user, ready, notice, login, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}
