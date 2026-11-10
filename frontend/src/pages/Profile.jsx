import { useState } from 'react';
import { api } from '../api.js';
import { useAuth } from '../auth.jsx';
import { useAction, useFetch } from '../hooks.js';
import { MAX_AMOUNT, formatPercent } from '../format.js';
import LocationFields from '../components/LocationFields.jsx';
import { Badge, Field, PageHeader, Section } from '../components/ui.jsx';

const VERIFICATION = {
  pending: { label: 'Waiting for approval', tone: 'warn' },
  verified: { label: 'Verified', tone: 'success' },
  rejected: { label: 'Not approved', tone: 'danger' },
};

function ReliabilityCard({ userId }) {
  const { data, error } = useFetch(() => api.reliability(userId));
  if (error || !data) return null;
  const resolved = data.fulfilled_count + data.no_show_count;
  return (
    <Section title="Your reliability">
      <div className="panel panel-padded">
        <p className="stat">{formatPercent(data.score)}</p>
        <p className="muted">
          {resolved === 0
            ? 'You have no completed pickups yet, so you start at a neutral 50%.'
            : `${data.fulfilled_count} collected, ${data.no_show_count} missed. Donors see this score, and a higher score makes matches more likely.`}
        </p>
      </div>
    </Section>
  );
}

function DetailsForm({ user }) {
  const { refreshUser } = useAuth();
  const [busy, run] = useAction();
  const [form, setForm] = useState({
    username: user.username,
    email: user.email,
    lat: user.location_lat != null ? String(user.location_lat) : '',
    lng: user.location_lng != null ? String(user.location_lng) : '',
    capacity: user.capacity != null ? String(user.capacity) : '',
  });
  const [error, setError] = useState('');
  const set = (changes) => setForm((current) => ({ ...current, ...changes }));

  async function submit(event) {
    event.preventDefault();
    setError('');
    if ((form.lat === '') !== (form.lng === '')) {
      setError('Enter both latitude and longitude, or leave both empty.');
      return;
    }

    // The API rejects explicit nulls, so only send fields that have a value.
    const changes = { username: form.username.trim(), email: form.email.trim() };
    if (form.lat !== '') {
      changes.location_lat = Number(form.lat);
      changes.location_lng = Number(form.lng);
    }
    if (user.role === 'recipient' && form.capacity !== '') changes.capacity = Number(form.capacity);

    await run(async () => {
      await api.updateMe(changes);
      await refreshUser();
    }, 'Details saved.');
  }

  return (
    <Section title="Your details">
      <form className="form" onSubmit={submit}>
        <Field label="Username">
          <input
            required
            minLength={3}
            maxLength={50}
            value={form.username}
            onChange={(event) => set({ username: event.target.value })}
          />
        </Field>
        <Field label="Email">
          <input
            type="email"
            required
            maxLength={100}
            value={form.email}
            onChange={(event) => set({ email: event.target.value })}
          />
        </Field>
        {user.role !== 'coordinator' && (
          <LocationFields
            label="Location"
            lat={form.lat}
            lng={form.lng}
            required={user.role === 'recipient'}
            onChange={({ lat, lng }) => set({ lat, lng })}
          />
        )}
        {user.role === 'recipient' && (
          <Field label="Capacity in portions">
            <input
              type="number"
              inputMode="decimal"
              step="any"
              min="0.1"
              max={MAX_AMOUNT}
              required
              value={form.capacity}
              onChange={(event) => set({ capacity: event.target.value })}
            />
          </Field>
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={busy}>
            Save changes
          </button>
        </div>
      </form>
    </Section>
  );
}

function PasswordForm() {
  const [busy, run] = useAction();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');

  async function submit(event) {
    event.preventDefault();
    const ok = await run(
      () => api.changePassword({ current_password: current, new_password: next }),
      'Password changed.',
    );
    if (ok) {
      setCurrent('');
      setNext('');
    }
  }

  return (
    <Section title="Change password">
      <form className="form" onSubmit={submit}>
        <Field label="Current password">
          <input
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
          />
        </Field>
        <Field label="New password" hint="At least 6 characters">
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={6}
            value={next}
            onChange={(event) => setNext(event.target.value)}
          />
        </Field>
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={busy}>
            Change password
          </button>
        </div>
      </form>
    </Section>
  );
}

export default function Profile() {
  const { user } = useAuth();
  const verification = VERIFICATION[user.verification_status];

  return (
    <>
      <PageHeader
        title="Your profile"
        intro={`Signed in as a ${user.is_organization ? 'organization ' : ''}${user.role}.`}
        action={verification && <Badge tone={verification.tone}>{verification.label}</Badge>}
      />
      {user.role === 'recipient' && <ReliabilityCard userId={user.id} />}
      <DetailsForm user={user} />
      <PasswordForm />
    </>
  );
}
