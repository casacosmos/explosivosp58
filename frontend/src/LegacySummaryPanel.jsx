import React from 'react';

/**
 * Lightweight JSX component that mirrors the Vue widget so existing
 * legacy dashboards can be compared against the new TypeScript pages.
 */
export function LegacySummaryPanel({ heading = 'Legacy Summary Panel', items = [] }) {
  return (
    <section className="legacy-summary-panel">
      <header>
        <h2>{heading}</h2>
      </header>
      <ul>
        {items.length === 0 && <li className="placeholder">No items to display.</li>}
        {items.map((item) => (
          <li key={item.id ?? item.label}>
            <strong>{item.label}</strong>
            {item.value && <span className="value">{item.value}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default LegacySummaryPanel;
