import { Link, NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../auth.jsx';
import { NotificationsProvider, useNotifications } from '../notifications.jsx';

const NAV_BY_ROLE = {
  donor: [
    { to: '/donations', label: 'Donations' },
    { to: '/pickups', label: 'Pickups' },
  ],
  recipient: [{ to: '/offers', label: 'Offers' }],
  coordinator: [{ to: '/coordinator', label: 'Coordinator' }],
};

function OrganizationBanner({ user }) {
  if (!user.is_organization) return null;
  if (user.verification_status === 'pending') {
    return (
      <div className="banner" data-tone="warn" role="status">
        Your organization is waiting for approval by a coordinator.{' '}
        {user.role === 'donor'
          ? 'You can post donations once it is approved.'
          : 'You can be matched with donations once it is approved.'}
      </div>
    );
  }
  if (user.verification_status === 'rejected') {
    return (
      <div className="banner" data-tone="danger" role="status">
        A coordinator did not approve your organization, so you cannot{' '}
        {user.role === 'donor' ? 'post donations' : 'be matched with donations'}.
      </div>
    );
  }
  return null;
}

function Shell() {
  const { user, logout } = useAuth();
  const { unread } = useNotifications();

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="app-header">
        <div className="app-header-inner">
          <Link to="/" className="brand">
            Food Redistribution
          </Link>
          <nav className="nav" aria-label="Main">
            {NAV_BY_ROLE[user.role].map((item) => (
              <NavLink key={item.to} to={item.to}>
                {item.label}
              </NavLink>
            ))}
            <NavLink to="/notifications">
              Notifications
              {unread > 0 && (
                <span className="nav-count" aria-label={`${unread} unread`}>
                  {unread}
                </span>
              )}
            </NavLink>
          </nav>
          <div className="header-user">
            <NavLink to="/profile" className="header-profile">
              {user.username}
            </NavLink>
            <button type="button" className="btn btn-link" onClick={logout}>
              Sign out
            </button>
          </div>
        </div>
      </header>
      <OrganizationBanner user={user} />
      <main id="main" className="container">
        <Outlet />
      </main>
    </>
  );
}

export default function Layout() {
  return (
    <NotificationsProvider>
      <Shell />
    </NotificationsProvider>
  );
}
