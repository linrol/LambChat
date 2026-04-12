/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Source Sans 3'", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
