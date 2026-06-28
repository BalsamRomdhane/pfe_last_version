import React from 'react';

/**
 * PageHero — standardised hero header for ML/Analytics pages.
 * Replaces the inconsistent dark gradient heroes with a unified enterprise look.
 */
const PageHero = ({ eyebrow, title, subtitle, badge, actions, children }) => {
  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-800 bg-gradient-to-r from-slate-900 via-slate-900 to-brand-950 px-6 py-6 shadow-lg">
      {/* Decorative orb */}
      <div className="pointer-events-none absolute right-0 top-0 h-full w-64 opacity-20"
        style={{ background: 'radial-gradient(ellipse at right top, #2563eb 0%, transparent 70%)' }}
      />

      <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          {children && (
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/10">
              {children}
            </div>
          )}
          <div>
            {eyebrow && (
              <p className="text-2xs font-bold uppercase tracking-[0.15em] text-brand-300 mb-1">{eyebrow}</p>
            )}
            <h1 className="text-xl font-bold text-white leading-tight">{title}</h1>
            {subtitle && <p className="mt-0.5 text-sm text-slate-400">{subtitle}</p>}
            {badge && <div className="mt-2">{badge}</div>}
          </div>
        </div>

        {actions && (
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
};

export default PageHero;
