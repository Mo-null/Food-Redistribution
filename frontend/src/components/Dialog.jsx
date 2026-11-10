import { useEffect, useRef } from 'react';
import { useAction } from '../hooks.js';

/** Modal built on the native <dialog>: focus trapping and Esc handling come from the browser. */
export default function Dialog({ title, onClose, children }) {
  const ref = useRef(null);

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  return (
    <dialog ref={ref} className="dialog" aria-labelledby="dialog-title" onClose={onClose}>
      <h2 id="dialog-title">{title}</h2>
      {children}
    </dialog>
  );
}

/** Asks for confirmation before running `onConfirm`; closes itself when that succeeds. */
export function ConfirmDialog({
  title,
  message,
  confirmLabel,
  tone = 'primary',
  successMessage,
  onConfirm,
  onClose,
}) {
  const [busy, run] = useAction();

  async function handleConfirm() {
    const ok = await run(onConfirm, successMessage);
    if (ok) onClose();
  }

  return (
    <Dialog title={title} onClose={onClose}>
      <p>{message}</p>
      <div className="dialog-actions">
        <button type="button" className="btn btn-secondary" onClick={onClose} disabled={busy}>
          Keep as is
        </button>
        <button
          type="button"
          className={`btn ${tone === 'danger' ? 'btn-danger' : 'btn-primary'}`}
          onClick={handleConfirm}
          disabled={busy}
        >
          {confirmLabel}
        </button>
      </div>
    </Dialog>
  );
}
