import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ["Geist Mono", "ui-monospace", "monospace"],
      },
      colors: {
        surface: "#0f0f0f",
        panel: "#161616",
        border: "#262626",
        muted: "#525252",
        text: "#e5e5e5",
        accent: "#a3e635",
        cites: "#525252",
        method: "#4ade80",
        bench: "#60a5fa",
        contradicts: "#f87171",
      },
    },
  },
  plugins: [],
};

export default config;
