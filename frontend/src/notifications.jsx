import { createContext, useCallback, useContext, useMemo } from 'react';
import { api } from './api.js';
import { useFetch } from './hooks.js';

const NotificationsContext = createContext(null);

/** One shared, auto-refreshing notification list for the header badge and the page. */
export function NotificationsProvider({ children }) {
  const { data, error, loading, reload } = useFetch(api.notifications, { poll: 30000 });
  const items = useMemo(() => data ?? [], [data]);
  const unread = items.filter((item) => !item.is_read).length;

  const markRead = useCallback(
    async (id) => {
      await api.markNotificationRead(id);
      await reload();
    },
    [reload],
  );

  const markAllRead = useCallback(async () => {
    const unreadItems = items.filter((item) => !item.is_read);
    await Promise.all(unreadItems.map((item) => api.markNotificationRead(item.id)));
    await reload();
  }, [items, reload]);

  const value = useMemo(
    () => ({ items, unread, error, loading, markRead, markAllRead }),
    [items, unread, error, loading, markRead, markAllRead],
  );

  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>;
}

export function useNotifications() {
  const context = useContext(NotificationsContext);
  if (!context) throw new Error('useNotifications must be used inside NotificationsProvider');
  return context;
}
