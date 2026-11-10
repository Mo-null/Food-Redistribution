import { useState } from 'react';
import { Field } from './ui.jsx';

/** Latitude and longitude inputs plus a button that fills them from the browser's location. */
export default function LocationFields({ lat, lng, onChange, required, label = 'Location' }) {
  const [message, setMessage] = useState('');
  const [locating, setLocating] = useState(false);

  function fillFromBrowserLocation() {
    if (!navigator.geolocation) {
      setMessage('Your browser cannot share its location. Enter the coordinates instead.');
      return;
    }
    setLocating(true);
    setMessage('');
    navigator.geolocation.getCurrentPosition(
      (position) => {
        onChange({
          lat: position.coords.latitude.toFixed(6),
          lng: position.coords.longitude.toFixed(6),
        });
        setLocating(false);
      },
      () => {
        setMessage('Could not get your location. Allow location access or enter the coordinates.');
        setLocating(false);
      },
      { timeout: 10000 },
    );
  }

  return (
    <fieldset className="fieldset">
      <legend>{label}</legend>
      <div className="field-pair">
        <Field label="Latitude">
          <input
            type="number"
            inputMode="decimal"
            step="any"
            min="-90"
            max="90"
            required={required}
            value={lat}
            onChange={(event) => onChange({ lat: event.target.value, lng })}
          />
        </Field>
        <Field label="Longitude">
          <input
            type="number"
            inputMode="decimal"
            step="any"
            min="-180"
            max="180"
            required={required}
            value={lng}
            onChange={(event) => onChange({ lat, lng: event.target.value })}
          />
        </Field>
      </div>
      <div className="location-actions">
        <button
          type="button"
          className="btn btn-secondary btn-small"
          onClick={fillFromBrowserLocation}
          disabled={locating}
        >
          {locating ? 'Finding your location…' : 'Use my current location'}
        </button>
        {message && <span className="field-error">{message}</span>}
      </div>
    </fieldset>
  );
}
