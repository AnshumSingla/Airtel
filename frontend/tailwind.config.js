/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { 50: "#eef6f4", 100: "#d5ebe6", 500: "#1f8a70", 600: "#18705b", 700: "#135a49", 900: "#0b3329" },
        ink: { 400: "#7a8580", 600: "#4a5550", 900: "#17201c" },
        warn: { 50: "#fff7e6", 600: "#a15c00" },
        bad: { 50: "#fdeeee", 600: "#b3261e" },
      },
      fontFamily: { sans: ["Inter", "Noto Sans Devanagari", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
