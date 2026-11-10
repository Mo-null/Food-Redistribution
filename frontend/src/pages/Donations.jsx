import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { useAuth } from '../auth.jsx';
import { useFetch } from '../hooks.js';
import { categoryLabel, donationStatus, formatDateTime, formatQuantity } from '../format.js';
import { ConfirmDialog } from '../components/Dialog.jsx';
import ExpiryBar from '../components/ExpiryBar.jsx';
import { DonationTitle } from '../components/MatchParts.jsx';
import { Badge, EmptyState, ErrorState, Loading, PageHeader, Section } from '../components/ui.jsx';

const OPEN_STATUSES = ['active', 'matched'];

function DonationRow({ donation, onChanged }) {
  const [cancelling, setCancelling] = useState(false);
  const status = donationStatus(donation);
  const isOpen = OPEN_STATUSES.includes(donation.status);
  const canEdit = donation.status === 'active' && status.label !== 'Expired';

  return (
    <li className="row">
      <div className="row-main">
        <DonationTitle donation={donation} />
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>
      {isOpen ? (
        <ExpiryBar start={donation.posted_at} end={donation.expiry_time} />
      ) : (
        <p className="row-meta-line muted">Posted {formatDateTime(donation.posted_at)}</p>
      )}
      {(canEdit || donation.status === 'matched') && (
        <div className="row-actions">
          {donation.status === 'matched' && (
            <Link className="btn btn-primary btn-small" to="/pickups">
              View pickup
            </Link>
          )}
          {canEdit && (
            <>
              <Link className="btn btn-secondary btn-small" to={`/donations/${donation.id}/edit`}>
                Edit
              </Link>
              <button
                type="button"
                className="btn btn-danger-outline btn-small"
                onClick={() => setCancelling(true)}
              >
                Cancel donation
              </button>
            </>
          )}
        </div>
      )}
      {cancelling && (
        <ConfirmDialog
          title="Cancel this donation?"
          message={`${donation.description || categoryLabel(donation.category)} (${formatQuantity(donation.quantity)}) will no longer be offered to recipients.`}
          confirmLabel="Cancel donation"
          tone="danger"
          successMessage="Donation cancelled."
          onConfirm={async () => {
            await api.cancelDonation(donation.id);
            await onChanged();
          }}
          onClose={() => setCancelling(false)}
        />
      )}
    </li>
  );
}

export default function Donations() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useFetch(api.myDonations, { poll: 30000 });

  const blocked = user.is_organization && user.verification_status !== 'verified';
  const postButton = blocked ? (
    <button
      type="button"
      className="btn btn-primary"
      disabled
      title="Your organization must be approved first"
    >
      Post a donation
    </button>
  ) : (
    <Link className="btn btn-primary" to="/donations/new">
      Post a donation
    </Link>
  );

  let content;
  if (loading) content = <Loading label="Loading your donations" />;
  else if (error) content = <ErrorState error={error} onRetry={reload} />;
  else if (data.length === 0) {
    content = (
      <EmptyState title="You have not posted any donations yet">
        Post surplus food and the platform will look for a recipient nearby.
      </EmptyState>
    );
  } else {
    const open = data
      .filter((donation) => OPEN_STATUSES.includes(donation.status))
      .sort((a, b) => new Date(a.expiry_time) - new Date(b.expiry_time));
    const past = data
      .filter((donation) => !OPEN_STATUSES.includes(donation.status))
      .sort((a, b) => new Date(b.posted_at) - new Date(a.posted_at));

    content = (
      <>
        <Section title="Open donations" count={open.length}>
          {open.length === 0 ? (
            <p className="muted">Nothing is open right now.</p>
          ) : (
            <ul className="panel">
              {open.map((donation) => (
                <DonationRow key={donation.id} donation={donation} onChanged={reload} />
              ))}
            </ul>
          )}
        </Section>
        {past.length > 0 && (
          <Section title="Past donations" count={past.length}>
            <ul className="panel">
              {past.map((donation) => (
                <DonationRow key={donation.id} donation={donation} onChanged={reload} />
              ))}
            </ul>
          </Section>
        )}
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Your donations"
        intro="Donations closest to expiring are listed first."
        action={postButton}
      />
      {content}
    </>
  );
}
