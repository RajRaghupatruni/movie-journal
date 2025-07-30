/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Poppins', 'sans-serif'],         // Default body font
        title: ['Poppins', 'sans-serif'],        // Optional: special use for headers
      },
    },
  },
  plugins: [require('@tailwindcss/line-clamp')],
};
