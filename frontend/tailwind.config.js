/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      screens: {
        // The Check Review two-pane console only fits when the window is both
        // wide and tall; otherwise we fall back to natural page scroll so every
        // control stays reachable.
        xltall: { raw: '(min-width: 1280px) and (min-height: 1000px)' },
      },
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        bank: {
          navy: '#0a1628',
          blue: '#1e3a5f',
          gold: '#c5a047',
          light: '#f8fafc',
        },
      },
    },
  },
  plugins: [],
}
