/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eff6ff",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
        },
        signal: {
          buy: "#22c55e",
          sell: "#ef4444",
          hold: "#f59e0b",
          neutral: "#6b7280",
        },
      },
    },
  },
  plugins: [],
};
