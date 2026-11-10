import { useCallback, useEffect, useRef, useState } from 'react';
import { useToast } from './toast.jsx';

/**
 * Loads data with `fn` on mount. With `poll` (ms) it also refreshes quietly in the background
 * and when the tab becomes visible again. `reload()` refreshes without a loading flash.
 */
export function useFetch(fn, { poll = 0 } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const fnRef = useRef(fn);
  const latest = useRef(0);
  const mounted = useRef(true);

  useEffect(() => {
    fnRef.current = fn;
  });

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const load = useCallback(async (quiet) => {
    latest.current += 1;
    const ticket = latest.current;
    if (!quiet) setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const data = await fnRef.current();
      if (mounted.current && ticket === latest.current) {
        setState({ data, error: null, loading: false });
      }
    } catch (error) {
      if (!mounted.current || ticket !== latest.current) return;
      // A failed background refresh keeps what is already on screen.
      if (quiet)
        setState((current) => (current.data ? current : { ...current, error, loading: false }));
      else setState({ data: null, error, loading: false });
    }
  }, []);

  useEffect(() => {
    load(false);
    if (!poll) return undefined;
    const timer = setInterval(() => load(true), poll);
    const onVisible = () => {
      if (document.visibilityState === 'visible') load(true);
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [load, poll]);

  const reload = useCallback(() => load(true), [load]);
  return { ...state, reload };
}

/** Current time in ms, refreshed every `intervalMs`. */
export function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return now;
}

/**
 * Runs an async action with a busy flag. Failures show an error toast and return false;
 * success optionally shows a toast and returns true.
 */
export function useAction() {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const run = useCallback(
    async (action, successMessage) => {
      setBusy(true);
      try {
        await action();
        if (successMessage) toast.success(successMessage);
        return true;
      } catch (error) {
        toast.error(error.message);
        return false;
      } finally {
        setBusy(false);
      }
    },
    [toast],
  );

  return [busy, run];
}
