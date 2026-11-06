/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          '"PingFang SC"',
          '"Hiragino Sans GB"',
          '"Microsoft YaHei"',
          'sans-serif',
        ],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        ink: {
          50: '#f7f8fa',
          100: '#eef0f4',
          200: '#dde1e9',
          300: '#c2c8d4',
          400: '#8f98a8',
          500: '#6b7484',
          600: '#4b5464',
          700: '#343c4b',
          800: '#1f2532',
          900: '#121722',
        },
        brand: {
          50: '#eef1ff',
          100: '#e0e5ff',
          200: '#c7ceff',
          300: '#a3adff',
          400: '#7f83fb',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#372f9e',
          900: '#2b2678',
        },
      },
      boxShadow: {
        card: '0 1px 2px rgba(18, 23, 34, 0.04), 0 8px 24px -12px rgba(18, 23, 34, 0.12)',
        pop: '0 12px 40px -12px rgba(18, 23, 34, 0.24)',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        pulseline: {
          '0%, 100%': { opacity: '0.35' },
          '50%': { opacity: '1' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.28s ease-out both',
        shimmer: 'shimmer 1.6s infinite',
        pulseline: 'pulseline 1.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
