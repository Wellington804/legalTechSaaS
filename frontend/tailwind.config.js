/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        serif: ['Georgia', 'Times New Roman', 'serif'],
        sans: ['system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Consolas', 'monospace'],
      },
      colors: {
        background: '#09090b',
        foreground: '#f4f4f5',
        card: {
          DEFAULT: '#121215',
          foreground: '#f4f4f5',
        },
        primary: {
          DEFAULT: '#2563eb',
          hover: '#1d4ed8',
          foreground: '#ffffff',
        },
        muted: {
          DEFAULT: '#27272a',
          foreground: '#a1a1aa',
        },
        accent: {
          DEFAULT: '#1e293b',
          foreground: '#f8fafc',
        },
        border: '#27272a',
      },
    },
  },
  plugins: [],
}
