import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        s1: 'var(--s1)',
        s2: 'var(--s2)',
        s3: 'var(--s3)',
        s4: 'var(--s4)',
        s5: 'var(--s5)',
        tx: 'var(--tx)',
        tx2: 'var(--tx2)',
        tx3: 'var(--tx3)',
        ac: 'var(--ac)',
        gn: 'var(--gn)',
        rd: 'var(--rd)',
        yl: 'var(--yl)',
        or: 'var(--or)',
        pp: 'var(--pp)',
        cy: 'var(--cy)',
      },
      fontSize: {
        'hero': ['96px', { lineHeight: '0.95', letterSpacing: '-0.04em', fontWeight: '700' }],
        'title': ['48px', { lineHeight: '1.08', letterSpacing: '-0.03em', fontWeight: '600' }],
        'body': ['17px', { lineHeight: '1.47', letterSpacing: '-0.022em' }],
        'caption': ['13px', { lineHeight: '1.38', letterSpacing: '-0.008em' }],
        'micro': ['11px', { lineHeight: '1.27', letterSpacing: '0.005em' }],
        'nano': ['10px', { lineHeight: '1.2', letterSpacing: '0.01em' }],
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'SF Pro Display', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['SF Mono', 'JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '16px',
        xs: '8px',
        sm: '12px',
        lg: '20px',
        xl: '24px',
        '2xl': '28px',
      },
      backdropBlur: {
        glass: '20px',
        strong: '40px',
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'pulse-slow': 'pulse-slow 4s ease-in-out infinite',
        'glow': 'glow 2s ease-in-out infinite',
        'fade-in-up': 'fade-in-up 0.5s ease-out both',
        'scale-in': 'scale-in 0.3s ease-out both',
        'slide-in-right': 'slide-in-right 0.3s ease-out both',
        'gradient-shift': 'gradient-shift 4s ease-in-out infinite',
        'source-flash': 'source-flash 0.8s ease-out',
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}

export default config
