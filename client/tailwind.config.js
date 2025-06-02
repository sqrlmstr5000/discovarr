/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'aiarr': {
          DEFAULT: '#1d8bfa',
          600: '#1d8bfa'
        }
      }
    },
  },
  plugins: [],
}
