import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(({ command }) => ({
  plugins: [
    {
      name: 'development-style-csp',
      transformIndexHtml(html: string) {
        return command === 'serve'
          ? html.replace("style-src 'self';", "style-src 'self' 'unsafe-inline';")
          : html
      },
    },
    react(),
    VitePWA({
      registerType: 'prompt',
      includeAssets: ['icon.svg', 'icon-maskable.svg'],
      manifest: {
        name: 'Personal Academic Intelligence Assistant',
        short_name: 'Academic Assistant',
        description: 'A private, student-owned academic dashboard.',
        theme_color: '#0a101c',
        background_color: '#0a101c',
        display: 'standalone',
        start_url: '/',
        icons: [
          {
            src: '/icon.svg',
            sizes: 'any',
            type: 'image/svg+xml',
            purpose: 'any',
          },
          {
            src: '/icon-maskable.svg',
            sizes: 'any',
            type: 'image/svg+xml',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
        runtimeCaching: [],
      },
    }),
  ],
}))

