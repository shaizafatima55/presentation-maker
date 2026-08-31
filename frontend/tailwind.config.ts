import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        'app-bg': '#0C0C0F',
        'app-surface': '#141417',
        'app-card': '#1A1A1F',
        'app-border': '#232329',
        'app-text': '#F0F0F5',
        'app-muted': '#8A8A9A',
        'app-accent': '#7C6FE0',
        'app-accent-hover': '#6B5FD0',
      }
    },
  },
  plugins: [],
};
export default config;
