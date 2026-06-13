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
        surface: "#f6f0e6",
        panel: "#fdf8ef",
        border: "#d8ccb8",
        muted: "#7a6f61",
        text: "#2f2923",
        accent: "#9b7b4f",
        cites: "#9a8f80",
        method: "#3f8f6b",
        bench: "#356e9b",
        contradicts: "#b35c4b",
      },
    },
  },
  plugins: [],
};

export default config;
