import {
  categoryLabel,
  formatCoordinates,
  formatQuantity,
  formatPercent,
  mapUrl,
} from '../format.js';
import { Badge } from './ui.jsx';

/** Title and subtitle shared by every row that shows a donation. */
export function DonationTitle({ donation }) {
  return (
    <div>
      <p className="row-title">{donation.description || categoryLabel(donation.category)}</p>
      <p className="row-sub">
        {categoryLabel(donation.category)}, {formatQuantity(donation.quantity)}
      </p>
    </div>
  );
}

/** Who is on the other side of a match: name, type and verification. */
export function CounterpartBadges({ counterpart }) {
  if (!counterpart) return null;
  return (
    <>
      <Badge>{counterpart.is_organization ? 'Organization' : 'Individual'}</Badge>
      {counterpart.is_organization && counterpart.verification_status === 'verified' && (
        <Badge tone="success">Verified</Badge>
      )}
    </>
  );
}

/** Reliability as the donor sees it for a recipient. */
export function ReliabilityText({ counterpart }) {
  const size = counterpart?.reliability_sample_size;
  if (counterpart?.reliability_score == null) return null;
  if (!size) return <span>New recipient, no pickups yet.</span>;
  return (
    <span>
      Reliability {formatPercent(counterpart.reliability_score)} over {size}{' '}
      {size === 1 ? 'pickup' : 'pickups'}.
    </span>
  );
}

/** Pickup location, with a note when it is only approximate. */
export function LocationLine({ donation }) {
  const approximate = donation.location_is_approximate;
  const { location_lat: lat, location_lng: lng } = donation;
  return (
    <p className="row-meta-line">
      {approximate ? 'Approximate area' : 'Pickup location'}:{' '}
      {formatCoordinates(lat, lng, approximate ? 2 : 5)}{' '}
      <a href={mapUrl(lat, lng)} target="_blank" rel="noreferrer">
        Open in maps
      </a>
      {approximate && (
        <span className="muted">
          {' '}
          (within about 1 km). The exact spot appears after you accept.
        </span>
      )}
    </p>
  );
}
