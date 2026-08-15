/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        serif: ['var(--font-playfair)', 'Merriweather', 'Georgia', 'serif'],
        sans: ['var(--font-inter)', 'var(--font-outfit)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'monospace'],
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
