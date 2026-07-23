/** @type {import('tailwindcss').Config} */

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    container: {
      center: true,
    },
    extend: {
      colors: {
        space: "var(--bg-space)",
        panel: "var(--bg-panel)",
        "panel-2": "var(--bg-panel-2)",
        elevated: "var(--bg-elevated)",
        inset: "var(--bg-inset)",
        subtle: "var(--border-subtle)",
        strong: "var(--border-strong)",
        ink: "var(--text-primary)",
        "ink-2": "var(--text-secondary)",
        "ink-3": "var(--text-muted)",
        accent: "var(--accent)",
        "accent-dim": "var(--accent-dim)",
        up: "var(--up)",
        "up-dim": "var(--up-dim)",
        down: "var(--down)",
        "down-dim": "var(--down-dim)",
        info: "var(--blue)",
        "info-dim": "var(--blue-dim)",
        amber: "var(--amber)",
        violet: "var(--violet)",
      },
      fontFamily: {
        display: "var(--font-display)",
        mono: "var(--font-mono)",
        sans: "var(--font-sans)",
      },
      borderRadius: {
        sm: "var(--r-sm)",
        md: "var(--r-md)",
        lg: "var(--r-lg)",
      },
      fontSize: {
        "2xs": ["10px", "14px"],
        xs: ["11px", "15px"],
      },
    },
  },
  plugins: [],
};
