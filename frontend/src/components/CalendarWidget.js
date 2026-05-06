import React from 'react';

export default function CalendarWidget() {
  const now = new Date();
  const dayNum = now.getDate();
  const month = now.toLocaleDateString('en-US', { month: 'long' }).toUpperCase();
  const weekday = now.toLocaleDateString('en-US', { weekday: 'long' });
  const year = now.getFullYear();

  // Build week row
  const dayOfWeek = now.getDay();
  const startOfWeek = new Date(now);
  startOfWeek.setDate(now.getDate() - dayOfWeek);
  const weekDays = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(startOfWeek);
    d.setDate(startOfWeek.getDate() + i);
    return d.getDate();
  });

  return (
    <div className="border border-cyan-900/50 p-4 text-center" data-testid="calendar-widget">
      <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400 mb-2">Calendar</h3>
      <div className="font-display text-4xl font-bold text-cyan-400" style={{ textShadow: '0 0 20px rgba(6,182,212,0.4)' }}>
        {dayNum}
      </div>
      <div className="font-display text-xs tracking-[0.3em] text-cyan-300/60 uppercase mt-1">{month}</div>
      <div className="font-mono text-[10px] text-cyan-300/40 mt-0.5">{weekday}</div>
      <div className="font-mono text-[9px] text-cyan-900 mt-0.5">{year}</div>

      {/* Week row */}
      <div className="flex justify-center gap-1.5 mt-3">
        {weekDays.map((day, i) => (
          <div
            key={i}
            className={`w-6 h-6 flex items-center justify-center text-[9px] font-mono border ${
              day === dayNum
                ? 'border-cyan-400 text-cyan-400 bg-cyan-950/40'
                : 'border-cyan-900/30 text-cyan-300/30'
            }`}
          >
            {day}
          </div>
        ))}
      </div>
    </div>
  );
}
