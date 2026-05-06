import React from 'react';
import { Cloud, Droplets, Wind } from 'lucide-react';

export default function WeatherWidget({ weather }) {
  if (!weather || weather.error) {
    return (
      <div className="relative border border-cyan-900/50 p-4 overflow-hidden" data-testid="weather-widget">
        <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400 mb-3">Weather</h3>
        <div className="text-cyan-900 text-xs font-mono">Acquiring satellite data...</div>
      </div>
    );
  }

  return (
    <div className="relative border border-cyan-900/50 p-4 overflow-hidden" data-testid="weather-widget">
      {/* Background image */}
      <div className="absolute inset-0 opacity-10" style={{
        backgroundImage: 'url(https://images.pexels.com/photos/30596263/pexels-photo-30596263.jpeg?auto=compress&w=400)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }} />
      <div className="absolute inset-0 bg-gradient-to-b from-slate-950/80 to-slate-950/95" />

      <div className="relative z-10">
        <h3 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-400 mb-3">Weather</h3>

        <div className="text-center mb-3">
          <div className="font-display text-3xl font-bold text-white" style={{ textShadow: '0 0 15px rgba(6,182,212,0.3)' }}>
            {weather.temp_c}<span className="text-lg text-cyan-300/60">°C</span>
          </div>
          <div className="font-mono text-xs text-cyan-400 mt-1">{weather.description}</div>
          <div className="font-display text-[9px] tracking-widest text-cyan-300/40 uppercase mt-1">
            {weather.location}, {weather.country}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="border border-cyan-900/30 p-2 text-center">
            <div className="font-display text-[7px] tracking-widest text-cyan-300/40 uppercase">Humidity</div>
            <div className="font-mono text-xs text-cyan-100">{weather.humidity}%</div>
          </div>
          <div className="border border-cyan-900/30 p-2 text-center">
            <div className="font-display text-[7px] tracking-widest text-cyan-300/40 uppercase">Wind</div>
            <div className="font-mono text-xs text-cyan-100">{weather.wind_speed} km/h</div>
          </div>
          <div className="border border-cyan-900/30 p-2 text-center">
            <div className="font-display text-[7px] tracking-widest text-cyan-300/40 uppercase">Feels Like</div>
            <div className="font-mono text-xs text-cyan-100">{weather.feels_like}°C</div>
          </div>
          <div className="border border-cyan-900/30 p-2 text-center">
            <div className="font-display text-[7px] tracking-widest text-cyan-300/40 uppercase">Direction</div>
            <div className="font-mono text-xs text-cyan-100">{weather.wind_dir}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
