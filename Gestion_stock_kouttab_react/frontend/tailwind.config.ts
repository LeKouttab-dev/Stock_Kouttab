import type { Config } from 'tailwindcss';

/**
 * Charte graphique "Le Kouttâb"
 * Palette officielle (couleur de base = nuance 500 sauf cream qui est ~100) :
 *   forest      #3d4f3d  → textes, headings, sidebar foncée
 *   terracotta  #ac724a  → PRIMARY (CTA, liens, focus)
 *   sage        #c4d7b2  → secondary, success-like
 *   sand        #d7bd9a  → surfaces secondaires, bordures soft
 *   cream       #eee4d3  → BACKGROUND principal (chaleureux)
 */
const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: ['class'],
  theme: {
    container: {
      center: true,
      padding: '1rem',
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
          50: '#fbf3ec',
          100: '#f3e1d1',
          200: '#e6c2a5',
          300: '#d6a079',
          400: '#c2855e',
          500: '#ac724a',
          600: '#955f3c',
          700: '#7b4d31',
          800: '#5e3b25',
          900: '#3f281a',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        success: {
          DEFAULT: '#86a373', // sage-700, success-like cohérent avec la charte
          foreground: '#ffffff',
        },
        warning: {
          DEFAULT: '#c2855e', // primary-400, plus chaleureux qu'un orange agressif
          foreground: '#ffffff',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        // Échelles custom (pour usages explicites bg-forest-500, text-sage-700, etc.)
        forest: {
          DEFAULT: '#3d4f3d',
          50: '#eef2ee',
          100: '#d6dfd6',
          200: '#aebfae',
          300: '#849c84',
          400: '#5e7c5e',
          500: '#3d4f3d',
          600: '#344533',
          700: '#2a382a',
          800: '#1f2b1f',
          900: '#141c14',
        },
        terracotta: {
          DEFAULT: '#ac724a',
          50: '#fbf3ec',
          100: '#f3e1d1',
          200: '#e6c2a5',
          300: '#d6a079',
          400: '#c2855e',
          500: '#ac724a',
          600: '#955f3c',
          700: '#7b4d31',
          800: '#5e3b25',
          900: '#3f281a',
        },
        sage: {
          DEFAULT: '#c4d7b2',
          50: '#f5f9f0',
          100: '#e7f0db',
          200: '#d6e4c4',
          300: '#c4d7b2',
          400: '#a8c08e',
          500: '#86a373',
          600: '#6b8359',
          700: '#546948',
          800: '#3f5037',
          900: '#293522',
        },
        sand: {
          DEFAULT: '#d7bd9a',
          50: '#faf5ed',
          100: '#f1e6d3',
          200: '#e7d4b8',
          300: '#d7bd9a',
          400: '#c5a479',
          500: '#b08960',
          600: '#917048',
          700: '#735738',
          800: '#544028',
          900: '#372a1a',
        },
        cream: {
          DEFAULT: '#eee4d3',
          50: '#fbf7ef',
          100: '#eee4d3',
          200: '#e3d3b8',
          300: '#d6bf99',
          400: '#c8aa7b',
          500: '#b89260',
          600: '#977548',
          700: '#735937',
          800: '#503e26',
          900: '#2e2316',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        serif: ['Fraunces', 'ui-serif', 'Georgia', 'serif'],
      },
      borderRadius: {
        lg: '0.6rem',
        md: '0.5rem',
        sm: '0.25rem',
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'fade-in': 'fade-in 0.2s ease-out',
      },
    },
  },
  plugins: [],
};

export default config;
