import { useState } from 'react';
import { api } from '../api.js';
import { useAction } from '../hooks.js';
import Dialog from './Dialog.jsx';
import { Field } from './ui.jsx';

const MIN_LENGTH = 5;
const MAX_LENGTH = 500;

/** Lets either party report a problem with a match to the coordinators. */
export default function DisputeDialog({ matchId, onClose }) {
  const [reason, setReason] = useState('');
  const [busy, run] = useAction();
  const tooShort = reason.trim().length < MIN_LENGTH;

  async function submit(event) {
    event.preventDefault();
    const ok = await run(
      () => api.createDispute(matchId, reason.trim()),
      'Report sent. A coordinator will review it.',
    );
    if (ok) onClose();
  }

  return (
    <Dialog title="Report a problem" onClose={onClose}>
      <form onSubmit={submit} className="form">
        <Field label="What went wrong?" hint={`${reason.length} of ${MAX_LENGTH} characters`}>
          <textarea
            rows={4}
            required
            minLength={MIN_LENGTH}
            maxLength={MAX_LENGTH}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </Field>
        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={busy || tooShort}>
            Send report
          </button>
        </div>
      </form>
    </Dialog>
  );
}
