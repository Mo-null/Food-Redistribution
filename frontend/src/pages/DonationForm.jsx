import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api.js';
import { useAuth } from '../auth.jsx';
import { useFetch } from '../hooks.js';
import { useToast } from '../toast.jsx';
import {
  CATEGORIES,
  MAX_AMOUNT,
  MAX_EXPIRY_HOURS,
  categoryLabel,
  toLocalInputValue,
} from '../format.js';
import LocationFields from '../components/LocationFields.jsx';
import { ErrorState, Field, Loading, PageHeader } from '../components/ui.jsx';

/** Checks the expiry the same way the API does, so the donor sees the problem before sending. */
function expiryProblem(value) {
  if (!value) return 'Choose when the food expires.';
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return 'Choose a valid date and time.';
  if (time <= Date.now()) return 'The expiry time must be in the future.';
  if (time > Date.now() + MAX_EXPIRY_HOURS * 3600 * 1000) {
    return `The expiry time cannot be more than ${MAX_EXPIRY_HOURS} hours from now.`;
  }
  return '';
}

function QuickFill({ onFilled }) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [warnings, setWarnings] = useState([]);

  async function fill() {
    setError('');
    setWarnings([]);
    setBusy(true);
    try {
      const result = await api.parseDonation(text.trim());
      onFilled(result);
      setWarnings(result.warnings);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="quickfill">
      <Field
        label="Describe it in your own words (optional)"
        hint="For example: 20 portions of rice and curry, good until 9pm. Check the filled-in form before posting."
      >
        <textarea
          rows={3}
          minLength={3}
          maxLength={500}
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
      </Field>
      <button
        type="button"
        className="btn btn-secondary btn-small"
        onClick={fill}
        disabled={busy || text.trim().length < 3}
      >
        {busy ? 'Reading your description…' : 'Fill in the form'}
      </button>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {warnings.length > 0 && (
        <ul className="form-notice-list" role="status">
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DonationFormBody({ donation }) {
  const isEdit = Boolean(donation);
  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [form, setForm] = useState(() => ({
    category: donation?.category ?? 'cooked_meals',
    description: donation?.description ?? '',
    quantity: donation ? String(donation.quantity) : '',
    expiry: donation ? toLocalInputValue(new Date(donation.expiry_time)) : '',
    lat: user.location_lat != null ? String(user.location_lat) : '',
    lng: user.location_lng != null ? String(user.location_lng) : '',
  }));
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [minExpiry] = useState(() => toLocalInputValue(new Date()));

  const set = (changes) => setForm((current) => ({ ...current, ...changes }));

  function applyParsed(result) {
    set({
      category: result.category,
      description: result.description,
      quantity: String(result.quantity_portions),
      expiry: toLocalInputValue(new Date(result.expiry_time)),
    });
  }

  async function submit(event) {
    event.preventDefault();
    setError('');

    const problem = expiryProblem(form.expiry);
    if (problem) {
      setError(problem);
      return;
    }

    const common = {
      category: form.category,
      description: form.description.trim() || null,
      quantity: Number(form.quantity),
      expiry_time: new Date(form.expiry).toISOString(),
    };

    setBusy(true);
    try {
      if (isEdit) {
        await api.updateDonation(donation.id, common);
        toast.success('Donation updated.');
      } else {
        await api.createDonation({
          ...common,
          location_lat: Number(form.lat),
          location_lng: Number(form.lng),
        });
        toast.success('Donation posted. Looking for a recipient now.');
      }
      navigate('/donations');
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <form className="form" onSubmit={submit}>
      {!isEdit && <QuickFill onFilled={applyParsed} />}

      <Field label="Type of food">
        <select value={form.category} onChange={(event) => set({ category: event.target.value })}>
          {CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {categoryLabel(category)}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Description (optional)" hint="Up to 255 characters">
        <input
          maxLength={255}
          value={form.description}
          onChange={(event) => set({ description: event.target.value })}
        />
      </Field>
      <Field label="Quantity in portions" hint="One portion is one meal for one person">
        <input
          type="number"
          inputMode="decimal"
          step="any"
          min="0.1"
          max={MAX_AMOUNT}
          required
          value={form.quantity}
          onChange={(event) => set({ quantity: event.target.value })}
        />
      </Field>
      <Field label="Food expires" hint="Up to 14 days from now">
        <input
          type="datetime-local"
          required
          min={minExpiry}
          value={form.expiry}
          onChange={(event) => set({ expiry: event.target.value })}
        />
      </Field>

      {isEdit ? (
        <p className="muted">
          The pickup location cannot be changed. To use a different place, cancel this donation and
          post a new one.
        </p>
      ) : (
        <LocationFields
          label="Pickup location"
          lat={form.lat}
          lng={form.lng}
          required
          onChange={({ lat, lng }) => set({ lat, lng })}
        />
      )}

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {isEdit ? 'Save changes' : 'Post donation'}
        </button>
        <Link className="btn btn-secondary" to="/donations">
          Cancel
        </Link>
      </div>
    </form>
  );
}

function EditDonation({ id }) {
  const { data, error, loading, reload } = useFetch(() => api.donation(id));
  const navigate = useNavigate();

  useEffect(() => {
    if (data && data.status !== 'active') navigate('/donations', { replace: true });
  }, [data, navigate]);

  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (data.status !== 'active') return null;
  return <DonationFormBody donation={data} />;
}

export default function DonationForm() {
  const { id } = useParams();
  const { user } = useAuth();
  const blocked = user.is_organization && user.verification_status !== 'verified';

  return (
    <>
      <PageHeader title={id ? 'Edit donation' : 'Post a donation'} />
      {blocked ? (
        <ErrorState
          error={{ message: 'Your organization must be approved before you can post donations.' }}
        />
      ) : id ? (
        <EditDonation id={id} />
      ) : (
        <DonationFormBody />
      )}
    </>
  );
}
