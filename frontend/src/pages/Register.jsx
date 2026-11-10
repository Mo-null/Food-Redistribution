import { useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { api } from '../api.js';
import { useAuth } from '../auth.jsx';
import { MAX_AMOUNT } from '../format.js';
import LocationFields from '../components/LocationFields.jsx';
import { Field } from '../components/ui.jsx';

const MAX_PASSWORD_BYTES = 72;

function toNumberOrNull(value) {
  return value === '' ? null : Number(value);
}

export default function Register() {
  const { user, ready, login } = useAuth();
  const [form, setForm] = useState({
    role: 'donor',
    username: '',
    email: '',
    password: '',
    isOrganization: false,
    lat: '',
    lng: '',
    capacity: '',
  });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (ready && user) return <Navigate to="/" replace />;

  const isRecipient = form.role === 'recipient';
  const set = (changes) => setForm((current) => ({ ...current, ...changes }));

  async function submit(event) {
    event.preventDefault();
    setError('');

    if (new TextEncoder().encode(form.password).length > MAX_PASSWORD_BYTES) {
      setError(
        `Password must be at most ${MAX_PASSWORD_BYTES} bytes. Non-English characters count as more than one.`,
      );
      return;
    }
    if ((form.lat === '') !== (form.lng === '')) {
      setError('Enter both latitude and longitude, or leave both empty.');
      return;
    }

    setBusy(true);
    try {
      await api.register({
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        role: form.role,
        is_organization: form.isOrganization,
        location_lat: toNumberOrNull(form.lat),
        location_lng: toNumberOrNull(form.lng),
        capacity: isRecipient ? toNumberOrNull(form.capacity) : null,
      });
      await login(form.username.trim(), form.password);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-intro">
        <h1>Create your account</h1>
        <p>
          Donors post surplus food. Recipients receive offers for it. Organizations are checked by a
          coordinator before they can take part.
        </p>
      </div>
      <form className="form auth-form" onSubmit={submit}>
        <fieldset className="fieldset">
          <legend>I want to</legend>
          <div className="choice-row">
            <label className="choice">
              <input
                type="radio"
                name="role"
                checked={form.role === 'donor'}
                onChange={() => set({ role: 'donor' })}
              />
              <span>Donate food</span>
            </label>
            <label className="choice">
              <input
                type="radio"
                name="role"
                checked={form.role === 'recipient'}
                onChange={() => set({ role: 'recipient' })}
              />
              <span>Receive food</span>
            </label>
          </div>
        </fieldset>

        <Field label="Username" hint="3 to 50 characters">
          <input
            autoComplete="username"
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
            autoComplete="email"
            required
            maxLength={100}
            value={form.email}
            onChange={(event) => set({ email: event.target.value })}
          />
        </Field>
        <Field label="Password" hint="At least 6 characters">
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={6}
            value={form.password}
            onChange={(event) => set({ password: event.target.value })}
          />
        </Field>

        <label className="choice">
          <input
            type="checkbox"
            checked={form.isOrganization}
            onChange={(event) => set({ isOrganization: event.target.checked })}
          />
          <span>
            I am registering an organization
            <span className="field-hint">
              {' '}
              A coordinator must approve it before you can take part.
            </span>
          </span>
        </label>

        <LocationFields
          label={isRecipient ? 'Your location' : 'Your usual pickup location (optional)'}
          lat={form.lat}
          lng={form.lng}
          required={isRecipient}
          onChange={({ lat, lng }) => set({ lat, lng })}
        />

        {isRecipient && (
          <Field
            label="Capacity in portions"
            hint="Roughly how much surplus food you can take at one time"
          >
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
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </button>
        <p className="form-switch">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </main>
  );
}
