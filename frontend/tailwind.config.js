/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        slate: {
          950: '#020617',
        },
        cyan: {
          350: '#67e8f9',
          450: '#22d3ee',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
        display: ['Azeret Mono', 'monospace'],
      },
      animation: {
        'spin-slow': 'spin 60s linear infinite',
        'spin-reverse': 'spin 45s linear infinite reverse',
      },
    },
  },
  plugins: [],
};
