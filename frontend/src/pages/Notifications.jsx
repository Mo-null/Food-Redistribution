import { useAction } from '../hooks.js';
import { useNotifications } from '../notifications.jsx';
import { formatDateTime } from '../format.js';
import { Badge, EmptyState, ErrorState, Loading, PageHeader } from '../components/ui.jsx';

export default function Notifications() {
  const { items, unread, error, loading, markRead, markAllRead } = useNotifications();
  const [busy, run] = useAction();

  let content;
  if (loading) content = <Loading label="Loading notifications" />;
  else if (error) content = <ErrorState error={error} />;
  else if (items.length === 0) {
    content = (
      <EmptyState title="No notifications yet">
        You will see updates here when a match, pickup or report changes.
      </EmptyState>
    );
  } else {
    content = (
      <ul className="panel">
        {items.map((item) => (
          <li
            key={item.id}
            className="row row-notification"
            data-unread={!item.is_read || undefined}
          >
            <div className="row-main">
              <div>
                <p className="row-title">{item.message}</p>
                <p className="row-sub">{formatDateTime(item.created_at)}</p>
              </div>
              {item.is_read ? (
                <Badge>Read</Badge>
              ) : (
                <button
                  type="button"
                  className="btn btn-secondary btn-small"
                  disabled={busy}
                  onClick={() => run(() => markRead(item.id))}
                >
                  Mark as read
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <>
      <PageHeader
        title="Notifications"
        intro={unread > 0 ? `${unread} unread` : 'You are all caught up.'}
        action={
          unread > 0 && (
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busy}
              onClick={() => run(markAllRead, 'All notifications marked as read.')}
            >
              Mark all as read
            </button>
          )
        }
      />
      {content}
    </>
  );
}
