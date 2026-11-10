import { useState } from 'react';
import { api } from '../api.js';
import { useAction, useFetch, useNow } from '../hooks.js';
import { formatCountdown, formatDateTime, matchStatus } from '../format.js';
import { ConfirmDialog } from '../components/Dialog.jsx';
import DisputeDialog from '../components/DisputeDialog.jsx';
import ExpiryBar from '../components/ExpiryBar.jsx';
import { CounterpartBadges, DonationTitle, LocationLine } from '../components/MatchParts.jsx';
import { Badge, EmptyState, ErrorState, Loading, PageHeader, Section } from '../components/ui.jsx';

/** Live countdown for the 30-minute window to answer an offer. */
function OfferTimer({ expiresAt }) {
  const now = useNow(1000);
  const left = new Date(expiresAt).getTime() - now;
  if (left <= 0) return <p className="row-meta-line muted">This offer has run out of time.</p>;
  return (
    <p className="row-meta-line">
      <span>
        Answer within <strong className="timer">{formatCountdown(left)}</strong>, or it goes to
        someone else.
      </span>
    </p>
  );
}

function OfferRow({ match, onChanged }) {
  const [busy, run] = useAction();
  const [dialog, setDialog] = useState(null);
  const now = useNow(match.status === 'proposed' ? 1000 : 60000);
  const status = matchStatus(match, 'recipient');
  const { donation, counterpart } = match;
  const timedOut =
    match.status === 'proposed' && new Date(match.proposal_expires_at).getTime() <= now;

  return (
    <li className="row">
      <div className="row-main">
        {donation ? <DonationTitle donation={donation} /> : <p className="row-title">Donation</p>}
        {timedOut ? (
          <Badge tone="neutral">No answer</Badge>
        ) : (
          <Badge tone={status.tone}>{status.label}</Badge>
        )}
      </div>

      <p className="row-meta-line">
        From {counterpart?.username ?? 'unknown'} <CounterpartBadges counterpart={counterpart} />
        {match.distance_km != null && <span className="muted"> {match.distance_km} km away</span>}
      </p>
      {donation && match.status !== 'rejected' && <LocationLine donation={donation} />}

      {match.status === 'proposed' && <OfferTimer expiresAt={match.proposal_expires_at} />}
      {(match.status === 'proposed' || match.status === 'accepted') && donation && (
        <ExpiryBar start={match.created_at} end={donation.expiry_time} />
      )}
      {match.status === 'accepted' && (
        <p className="row-meta-line muted">
          After you collect the food, the donor confirms the pickup.
        </p>
      )}
      {match.resolved_at && (
        <p className="row-meta-line muted">Closed {formatDateTime(match.resolved_at)}</p>
      )}

      <div className="row-actions">
        {match.status === 'proposed' && !timedOut && (
          <>
            <button
              type="button"
              className="btn btn-primary btn-small"
              disabled={busy}
              onClick={async () => {
                const ok = await run(
                  () => api.acceptMatch(match.id),
                  'Offer accepted. The exact pickup location is now shown.',
                );
                if (ok) await onChanged();
              }}
            >
              Accept offer
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-small"
              disabled={busy}
              onClick={() => setDialog('decline')}
            >
              Decline offer
            </button>
          </>
        )}
        {match.status !== 'proposed' && (
          <button
            type="button"
            className="btn btn-link btn-small"
            onClick={() => setDialog('dispute')}
          >
            Report a problem
          </button>
        )}
      </div>

      {dialog === 'decline' && (
        <ConfirmDialog
          title="Decline this offer?"
          message="The food goes back to the pool and will not be offered to you again."
          confirmLabel="Decline offer"
          tone="danger"
          successMessage="Offer declined."
          onConfirm={async () => {
            await api.declineMatch(match.id);
            await onChanged();
          }}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog === 'dispute' && <DisputeDialog matchId={match.id} onClose={() => setDialog(null)} />}
    </li>
  );
}

function OfferList({ title, matches, onChanged }) {
  if (matches.length === 0) return null;
  return (
    <Section title={title} count={matches.length}>
      <ul className="panel">
        {matches.map((match) => (
          <OfferRow key={match.id} match={match} onChanged={onChanged} />
        ))}
      </ul>
    </Section>
  );
}

const newestFirst = (a, b) => new Date(b.created_at) - new Date(a.created_at);

export default function Offers() {
  const { data, error, loading, reload } = useFetch(api.matches, { poll: 30000 });

  let content;
  if (loading) content = <Loading label="Loading your offers" />;
  else if (error) content = <ErrorState error={error} onRetry={reload} />;
  else if (data.length === 0) {
    content = (
      <EmptyState title="No offers yet">
        Matching runs every 10 minutes and whenever a donor posts food. An offer appears here as
        soon as there is a good fit nearby.
      </EmptyState>
    );
  } else {
    const byStatus = (...statuses) =>
      data.filter((match) => statuses.includes(match.status)).sort(newestFirst);
    content = (
      <>
        <OfferList
          title="Waiting for your answer"
          matches={byStatus('proposed')}
          onChanged={reload}
        />
        <OfferList title="Accepted" matches={byStatus('accepted')} onChanged={reload} />
        <OfferList title="History" matches={byStatus('fulfilled', 'rejected')} onChanged={reload} />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Offers"
        intro="You can hold one open offer at a time. This page refreshes on its own."
      />
      {content}
    </>
  );
}
