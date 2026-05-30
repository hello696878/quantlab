import type { Config } from "tailwindcss";

/**
 * QuantLab v2 dark theme.
 *
 * The existing components were authored against the default (light) Tailwind
 * palette.  Rather than rewrite every component, the slate / blue / red /
 * green / emerald / amber scales are remapped here to dark-terminal values.
 * Because the colours are supplied as hex, every opacity modifier (`/60`),
 * hover variant, and arbitrary usage resolves to the dark value automatically.
 *
 * Role of each remapped scale:
 *   slate  — inverted ramp: 50/100/200 = dark surfaces & hairlines,
 *            400/500/600 = muted→body text, 700/800/900 = bright text.
 *   blue   — electric-blue accent (buttons, links, highlights).
 *   red    — losses / errors (kept light enough to read on dark).
 *   green/emerald — gains.   amber — warnings.
 *
 * `white` is intentionally NOT remapped (text-white must stay white on
 * coloured buttons); `bg-white` is handled by a CSS override in globals.css.
 */
const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Equity-chart line colours (also referenced by some components).
        strategy: "#4d8bff",
        benchmark: "#8b95ab",

        // ---- Inverted, dark-mode slate ramp --------------------------------
        slate: {
          50: "#10172a", // darkest inner surface
          100: "#161e33", // elevated surface / faint border
          200: "#232c44", // hairline border
          300: "#354060", // stronger border / faintest text
          400: "#6f7a92", // muted text
          500: "#8b95ab", // secondary text
          600: "#a6afc4", // body text
          700: "#c3cbdb",
          800: "#d8dde9",
          900: "#e8ecf6", // primary text (brightest)
          950: "#f3f5fb",
        },

        // ---- Electric-blue accent ------------------------------------------
        blue: {
          50: "#0e1c3e",
          100: "#13284f",
          200: "#1b3a6e",
          300: "#27508f",
          400: "#5b9bff",
          500: "#4d8bff",
          600: "#3b82f6", // primary button base
          700: "#4d8bff", // hover + accent text (legible on dark)
          800: "#2f6fe0", // active (deeper)
          900: "#21509c",
          950: "#16204a",
        },

        // ---- Losses / errors (rose) ----------------------------------------
        red: {
          50: "#2a1316",
          100: "#3a191d",
          200: "#582027", // border
          300: "#6e2a31",
          400: "#fb7185",
          500: "#f86b74",
          600: "#f8717f", // body error text
          700: "#fca5b0", // heading error text (lighter)
          800: "#7d2b30",
          900: "#5e2126",
          950: "#2a1011",
        },

        // ---- Gains (green) -------------------------------------------------
        green: {
          50: "#0c2418",
          100: "#0f2a1d",
          200: "#1d4d39",
          300: "#2a6b50",
          400: "#34d399",
          500: "#34d399",
          600: "#34d399",
          700: "#5ee9b0",
          800: "#86efc0",
          900: "#1d4d39",
          950: "#08160e",
        },

        // ---- Gains (emerald) ----------------------------------------------
        emerald: {
          50: "#0c2418",
          100: "#0f2a1d",
          200: "#1d4d39",
          300: "#2a6b50",
          400: "#2ee0a8",
          500: "#2ee0a8",
          600: "#2ee0a8",
          700: "#5fe7bc",
          800: "#8af0cf",
          900: "#1d4d39",
          950: "#08160e",
        },

        // ---- Warnings (amber) ---------------------------------------------
        amber: {
          50: "#2a2110",
          100: "#3a2d12",
          200: "#5a4520",
          300: "#6b521f",
          400: "#fbbf24",
          500: "#fbbf24",
          600: "#f5b014",
          700: "#fcd34d",
          800: "#fde08a",
          900: "#5a4520",
          950: "#2a2110",
        },
      },
      fontFamily: {
        sans: ["var(--font-ui)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: {
        xl: "18px",
        "2xl": "24px",
      },
      boxShadow: {
        sm: "0 1px 2px rgba(0,0,0,0.4)",
        md: "0 4px 16px rgba(0,0,0,0.35), 0 1px 2px rgba(0,0,0,0.4)",
        lg: "0 18px 50px -12px rgba(0,0,0,0.65), 0 2px 8px rgba(0,0,0,0.4)",
      },
    },
  },
  plugins: [],
};

export default config;
