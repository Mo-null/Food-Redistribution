import { useState } from 'react';
import { api } from '../api.js';
import { useAction, useFetch } from '../hooks.js';
import { formatDateTime, matchStatus } from '../format.js';
import Dialog from '../components/Dialog.jsx';
import DisputeDialog from '../components/DisputeDialog.jsx';
import ExpiryBar from '../components/ExpiryBar.jsx';
import { CounterpartBadges, DonationTitle, ReliabilityText } from '../components/MatchParts.jsx';
import { Badge, EmptyState, ErrorState, Loading, PageHeader, Section } from '../components/ui.jsx';

function FailedPickupDialog({ match, onClose, onChanged }) {
  const [recipientAtFault, setRecipientAtFault] = useState(null);
  const [busy, run] = useAction();

  async function submit(event) {
    event.preventDefault();
    const ok = await run(async () => {
      await api.rejectMatch(match.id, recipientAtFault);
      await onChanged();
    }, 'Pickup closed. The donation is available for matching again.');
    if (ok) onClose();
  }

  return (
    <Dialog title="The pickup did not happen" onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <fieldset className="fieldset">
          <legend>What happened?</legend>
          <label className="choice">
            <input
              type="radio"
              name="fault"
              checked={recipientAtFault === true}
              onChange={() => setRecipientAtFault(true)}
            />
            <span>
              The recipient did not come
              <span className="field-hint"> This lowers their reliability score.</span>
            </span>
          </label>
          <label className="choice">
            <input
              type="radio"
              name="fault"
              checked={recipientAtFault === false}
              onChange={() => setRecipientAtFault(false)}
            />
            <span>
              It fell through for another reason
              <span className="field-hint"> Nobody is penalised.</span>
            </span>
          </label>
        </fieldset>
        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            type="submit"
            className="btn btn-danger"
            disabled={busy || recipientAtFault === null}
          >
            Close pickup
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function PickupRow({ match, onChanged }) {
  const [busy, run] = useAction();
  const [dialog, setDialog] = useState(null);
  const status = matchStatus(match, 'donor');
  const { donation, counterpart } = match;

  return (
    <li className="row">
      <div className="row-main">
        {donation ? <DonationTitle donation={donation} /> : <p className="row-title">Donation</p>}
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>

      <p className="row-meta-line">
        Recipient {counterpart?.username ?? 'unknown'}{' '}
        <CounterpartBadges counterpart={counterpart} />
      </p>
      <p className="row-meta-line muted">
        <ReliabilityText counterpart={counterpart} />
        {match.distance_km != null && <span>{match.distance_km} km from you.</span>}
      </p>

      {match.status === 'proposed' && (
        <p className="row-meta-line muted">
          Waiting for an answer until {formatDateTime(match.proposal_expires_at)}.
        </p>
      )}
      {(match.status === 'proposed' || match.status === 'accepted') && donation && (
        <ExpiryBar start={match.created_at} end={donation.expiry_time} />
      )}
      {match.resolved_at && (
        <p className="row-meta-line muted">Closed {formatDateTime(match.resolved_at)}</p>
      )}

      <div className="row-actions">
        {match.status === 'accepted' && (
          <>
            <button
              type="button"
              className="btn btn-primary btn-small"
              disabled={busy}
              onClick={async () => {
                const ok = await run(
                  () => api.confirmMatch(match.id),
                  'Pickup confirmed. Thank you!',
                );
                if (ok) await onChanged();
              }}
            >
              Confirm pickup
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-small"
              disabled={busy}
              onClick={() => setDialog('failed')}
            >
              Pickup did not happen
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

      {dialog === 'failed' && (
        <FailedPickupDialog match={match} onChanged={onChanged} onClose={() => setDialog(null)} />
      )}
      {dialog === 'dispute' && <DisputeDialog matchId={match.id} onClose={() => setDialog(null)} />}
    </li>
  );
}

function PickupList({ title, matches, onChanged }) {
  if (matches.length === 0) return null;
  return (
    <Section title={title} count={matches.length}>
      <ul className="panel">
        {matches.map((match) => (
          <PickupRow key={match.id} match={match} onChanged={onChanged} />
        ))}
      </ul>
    </Section>
  );
}

const newestFirst = (a, b) => new Date(b.created_at) - new Date(a.created_at);

export default function Pickups() {
  const { data, error, loading, reload } = useFetch(api.matches, { poll: 30000 });

  let content;
  if (loading) content = <Loading label="Loading your pickups" />;
  else if (error) content = <ErrorState error={error} onRetry={reload} />;
  else if (data.length === 0) {
    content = (
      <EmptyState title="No pickups yet">
        When the platform finds a recipient for one of your donations, it appears here.
      </EmptyState>
    );
  } else {
    const byStatus = (...statuses) =>
      data.filter((match) => statuses.includes(match.status)).sort(newestFirst);
    content = (
      <>
        <PickupList
          title="Waiting for your confirmation"
          matches={byStatus('accepted')}
          onChanged={reload}
        />
        <PickupList
          title="Waiting for a recipient to answer"
          matches={byStatus('proposed')}
          onChanged={reload}
        />
        <PickupList
          title="History"
          matches={byStatus('fulfilled', 'rejected')}
          onChanged={reload}
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Pickups"
        intro="Confirm a pickup once the recipient has collected the food. This page refreshes on its own."
      />
      {content}
    </>
  );
}
