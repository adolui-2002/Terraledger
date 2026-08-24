/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#0B1614",
          soft: "#0E1B18",
        },
        surface: {
          DEFAULT: "#12211D",
          raised: "#182D27",
          hover: "#1D362F",
        },
        border: {
          DEFAULT: "#24413A",
          soft: "#1B2F29",
        },
        ink_text: {
          primary: "#EAF2EE",
          muted: "#8FA89E",
          faint: "#5E7A70",
        },
        gold: {
          DEFAULT: "#D4A54A",
          soft: "#E8C583",
          dim: "#8A6B2F",
        },
        moss: {
          DEFAULT: "#5FAE86",
          soft: "#8FCBAB",
          dim: "#2F5C43",
        },
        clay: {
          DEFAULT: "#C1584B",
          soft: "#DE8A7F",
          dim: "#6E2E26",
        },
        teal: {
          DEFAULT: "#3E8E92",
          soft: "#7FC1C4",
        },
      },
      fontFamily: {
        display: ["Fraunces", "ui-serif", "Georgia", "serif"],
        body: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(234,242,238,0.04) inset, 0 8px 24px -12px rgba(0,0,0,0.5)",
      },
      backgroundImage: {
        contour: "radial-gradient(circle at 20% 20%, rgba(212,165,74,0.08), transparent 40%)",
      },
    },
  },
  plugins: [],
};
