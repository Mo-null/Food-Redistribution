import { cloneElement, useId } from 'react';

export function Loading({ label = 'Loading' }) {
  return (
    <p className="loading" role="status">
      {label}…
    </p>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="state state-error" role="alert">
      <p>{error?.message || 'Something went wrong.'}</p>
      {onRetry && (
        <button type="button" className="btn btn-secondary btn-small" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }) {
  return (
    <div className="state">
      <p className="state-title">{title}</p>
      {children && <div className="state-body">{children}</div>}
    </div>
  );
}

export function Badge({ tone = 'neutral', children }) {
  return (
    <span className="badge" data-tone={tone}>
      {children}
    </span>
  );
}

/** A label, its control and optional hint or error, wired together for screen readers. */
export function Field({ label, hint, error, children }) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint && hintId, error && errorId].filter(Boolean).join(' ') || undefined;

  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      {cloneElement(children, { id, 'aria-describedby': describedBy })}
      {hint && (
        <span id={hintId} className="field-hint">
          {hint}
        </span>
      )}
      {error && (
        <span id={errorId} className="field-error">
          {error}
        </span>
      )}
    </div>
  );
}

export function PageHeader({ title, intro, action }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {intro && <p className="page-intro">{intro}</p>}
      </div>
      {action}
    </div>
  );
}

export function Section({ title, count, children }) {
  return (
    <section className="section">
      <h2>
        {title}
        {count !== undefined && <span className="section-count">{count}</span>}
      </h2>
      {children}
    </section>
  );
}
