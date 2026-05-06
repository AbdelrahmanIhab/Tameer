/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#2d7a3a',
        secondary: '#8b6914',
        bg: '#f5f2eb',
      },
    },
  },
  plugins: [],
};
