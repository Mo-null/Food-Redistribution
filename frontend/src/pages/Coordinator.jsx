import { useState } from 'react';
import { api } from '../api.js';
import { useAction, useFetch } from '../hooks.js';
import { categoryLabel, formatDateTime, formatQuantity, matchStatus } from '../format.js';
import { ConfirmDialog } from '../components/Dialog.jsx';
import { Badge, EmptyState, ErrorState, Loading, PageHeader, Section } from '../components/ui.jsx';

function MatchingControl() {
  const [busy, run] = useAction();
  const [result, setResult] = useState(null);

  async function runMatching() {
    let created = 0;
    const ok = await run(async () => {
      created = (await api.runMatching()).matches_created;
    });
    if (ok) setResult(created);
  }

  return (
    <Section title="Matching">
      <div className="panel panel-padded">
        <p>
          Matching runs by itself every 10 minutes and after each new donation. Run it now to pair
          waiting donations with recipients immediately.
        </p>
        <div className="row-actions">
          <button type="button" className="btn btn-primary" disabled={busy} onClick={runMatching}>
            {busy ? 'Running…' : 'Run matching now'}
          </button>
          {result !== null && (
            <span role="status">
              {result === 0
                ? 'Finished. No new matches were created.'
                : `Finished. ${result} new ${result === 1 ? 'match' : 'matches'} created.`}
            </span>
          )}
        </div>
      </div>
    </Section>
  );
}

function OrganizationRow({ organization, onChanged }) {
  const [busy, run] = useAction();
  const [rejecting, setRejecting] = useState(false);

  async function approve() {
    const ok = await run(
      () => api.verifyOrganization(organization.id, true),
      `${organization.username} approved.`,
    );
    if (ok) await onChanged();
  }

  return (
    <li className="row">
      <div className="row-main">
        <div>
          <p className="row-title">{organization.username}</p>
          <p className="row-sub">
            {organization.email}, registered as a {organization.role}
          </p>
        </div>
        <div className="row-actions">
          <button
            type="button"
            className="btn btn-primary btn-small"
            disabled={busy}
            onClick={approve}
          >
            Approve
          </button>
          <button
            type="button"
            className="btn btn-danger-outline btn-small"
            disabled={busy}
            onClick={() => setRejecting(true)}
          >
            Reject
          </button>
        </div>
      </div>
      {rejecting && (
        <ConfirmDialog
          title={`Reject ${organization.username}?`}
          message="They will not be able to post donations or be matched as a recipient."
          confirmLabel="Reject organization"
          tone="danger"
          successMessage={`${organization.username} rejected.`}
          onConfirm={async () => {
            await api.verifyOrganization(organization.id, false);
            await onChanged();
          }}
          onClose={() => setRejecting(false)}
        />
      )}
    </li>
  );
}

function Organizations() {
  const { data, error, loading, reload } = useFetch(api.pendingVerifications, { poll: 30000 });

  let content;
  if (loading) content = <Loading />;
  else if (error) content = <ErrorState error={error} onRetry={reload} />;
  else if (data.length === 0) content = <p className="muted">No organizations are waiting.</p>;
  else {
    content = (
      <ul className="panel">
        {data.map((organization) => (
          <OrganizationRow key={organization.id} organization={organization} onChanged={reload} />
        ))}
      </ul>
    );
  }

  return (
    <Section title="Organizations waiting for approval" count={data?.length}>
      {content}
    </Section>
  );
}

function MatchDetails({ matchId }) {
  const { data, error, loading } = useFetch(() => api.match(matchId));
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;
  const status = matchStatus(data, 'coordinator');
  const donation = data.donation;
  return (
    <div className="detail">
      <p className="row-meta-line">
        Match status <Badge tone={status.tone}>{status.label}</Badge>
        {data.resolved_at && (
          <span className="muted"> closed {formatDateTime(data.resolved_at)}</span>
        )}
      </p>
      {donation && (
        <p className="row-meta-line">
          <span>
            {donation.description || categoryLabel(donation.category)}.{' '}
            {categoryLabel(donation.category)}, {formatQuantity(donation.quantity)}. Food expires{' '}
            {formatDateTime(donation.expiry_time)}.
          </span>
        </p>
      )}
      {data.distance_km != null && (
        <p className="row-meta-line muted">Donor and recipient are {data.distance_km} km apart.</p>
      )}
    </div>
  );
}

function DisputeRow({ dispute, onChanged }) {
  const [busy, run] = useAction();
  const [showMatch, setShowMatch] = useState(false);

  async function resolve() {
    const ok = await run(() => api.resolveDispute(dispute.id), 'Report resolved.');
    if (ok) await onChanged();
  }

  return (
    <li className="row">
      <div className="row-main">
        <div>
          <p className="row-title">{dispute.reason}</p>
          <p className="row-sub">
            Reported {formatDateTime(dispute.created_at)} by user {dispute.reported_by.slice(0, 8)}
          </p>
        </div>
        <Badge tone="warn">Open</Badge>
      </div>
      {showMatch && <MatchDetails matchId={dispute.match_id} />}
      <div className="row-actions">
        <button
          type="button"
          className="btn btn-secondary btn-small"
          aria-expanded={showMatch}
          onClick={() => setShowMatch((open) => !open)}
        >
          {showMatch ? 'Hide match details' : 'Show match details'}
        </button>
        <button
          type="button"
          className="btn btn-primary btn-small"
          disabled={busy}
          onClick={resolve}
        >
          Mark as resolved
        </button>
      </div>
    </li>
  );
}

function Disputes() {
  const { data, error, loading, reload } = useFetch(api.disputes, { poll: 30000 });

  let content;
  if (loading) content = <Loading />;
  else if (error) content = <ErrorState error={error} onRetry={reload} />;
  else if (data.length === 0) {
    content = (
      <EmptyState title="No open reports">
        Donors and recipients can report a problem with a match. Reports appear here.
      </EmptyState>
    );
  } else {
    content = (
      <ul className="panel">
        {data.map((dispute) => (
          <DisputeRow key={dispute.id} dispute={dispute} onChanged={reload} />
        ))}
      </ul>
    );
  }

  return (
    <Section title="Open reports" count={data?.length}>
      {content}
    </Section>
  );
}

export default function Coordinator() {
  return (
    <>
      <PageHeader
        title="Coordinator"
        intro="Approve organizations, handle reports and run matching."
      />
      <Organizations />
      <Disputes />
      <MatchingControl />
    </>
  );
}
