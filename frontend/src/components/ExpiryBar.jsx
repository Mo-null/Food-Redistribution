import { useNow } from '../hooks.js';
import { formatDateTime, formatDuration } from '../format.js';

/**
 * The time left before food expires, drawn as a bar that empties from `start` to `end`.
 * It turns amber in the last two hours.
 */
export default function ExpiryBar({ start, end }) {
  const now = useNow(10000);
  const endMs = new Date(end).getTime();
  const total = Math.max(endMs - new Date(start).getTime(), 1);
  const left = endMs - now;
  const percent = Math.min(Math.max(left / total, 0), 1) * 100;
  const state = left <= 0 ? 'expired' : left < 2 * 3600 * 1000 ? 'urgent' : 'ok';

  return (
    <div className="expiry" data-state={state}>
      <div className="expiry-text">
        <span className="expiry-left">
          {state === 'expired' ? 'Expired' : `${formatDuration(left)} left`}
        </span>
        <span className="expiry-at">Food expires {formatDateTime(end)}</span>
      </div>
      <div className="expiry-track" aria-hidden="true">
        <div className="expiry-fill" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
