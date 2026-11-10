export const CATEGORY_LABELS = {
  cooked_meals: 'Cooked meals',
  raw_produce: 'Raw produce',
  bakery: 'Bakery',
  packaged: 'Packaged food',
  dairy_eggs: 'Dairy and eggs',
  meat_fish: 'Meat and fish',
  beverages: 'Beverages',
  other: 'Other',
};

export const CATEGORIES = Object.keys(CATEGORY_LABELS);

export function categoryLabel(category) {
  return CATEGORY_LABELS[category] || category;
}

const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
});

export function formatDateTime(iso) {
  if (!iso) return '';
  return dateTimeFormat.format(new Date(iso));
}

export function formatQuantity(quantity) {
  const text = Number.isInteger(quantity) ? String(quantity) : quantity.toFixed(1);
  return `${text} ${quantity === 1 ? 'portion' : 'portions'}`;
}

/** Human-readable length of time for a duration in milliseconds. */
export function formatDuration(ms) {
  const minutes = Math.floor(ms / 60000);
  if (minutes < 1) return 'less than a minute';
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) {
    const rest = minutes % 60;
    return rest ? `${hours} h ${rest} min` : `${hours} h`;
  }
  const days = Math.floor(hours / 24);
  const restHours = hours % 24;
  return restHours ? `${days} d ${restHours} h` : `${days} d`;
}

/** mm:ss countdown for short windows such as the 30-minute offer timer. */
export function formatCountdown(ms) {
  const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

export function formatPercent(fraction) {
  return `${Math.round(fraction * 100)}%`;
}

/** Value for <input type="datetime-local"> in the user's local time. */
export function toLocalInputValue(date) {
  const pad = (n) => String(n).padStart(2, '0');
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

export const MAX_EXPIRY_HOURS = 48 * 7;
export const MAX_AMOUNT = 10000;

/**
 * Label and tone for a donation. An "active" donation past its expiry is shown as expired,
 * because the server only flips that status on its next 10-minute round.
 */
export function donationStatus(donation, now = Date.now()) {
  const expired = new Date(donation.expiry_time).getTime() <= now;
  switch (donation.status) {
    case 'active':
      return expired
        ? { label: 'Expired', tone: 'danger' }
        : { label: 'Waiting for a match', tone: 'info' };
    case 'matched':
      return { label: 'Matched', tone: 'accent' };
    case 'fulfilled':
      return { label: 'Picked up', tone: 'success' };
    case 'expired':
      return { label: 'Expired', tone: 'danger' };
    case 'cancelled':
      return { label: 'Cancelled', tone: 'neutral' };
    default:
      return { label: donation.status, tone: 'neutral' };
  }
}

const OUTCOME_LABELS = {
  fulfilled: { label: 'Picked up', tone: 'success' },
  declined: { label: 'Declined', tone: 'neutral' },
  ignored: { label: 'No answer', tone: 'neutral' },
  no_show: { label: 'No-show', tone: 'danger' },
  withdrawn: { label: 'Withdrawn', tone: 'neutral' },
};

/** Label and tone for a match, from the viewer's side. */
export function matchStatus(match, role) {
  switch (match.status) {
    case 'proposed':
      return role === 'recipient'
        ? { label: 'New offer', tone: 'accent' }
        : { label: 'Offered', tone: 'info' };
    case 'accepted':
      return { label: 'Accepted', tone: 'accent' };
    case 'fulfilled':
      return OUTCOME_LABELS.fulfilled;
    case 'rejected':
      return OUTCOME_LABELS[match.outcome] || { label: 'Closed', tone: 'neutral' };
    default:
      return { label: match.status, tone: 'neutral' };
  }
}

export function formatCoordinates(lat, lng, decimals = 4) {
  return `${Number(lat).toFixed(decimals)}, ${Number(lng).toFixed(decimals)}`;
}

export function mapUrl(lat, lng) {
  return `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=16/${lat}/${lng}`;
}
