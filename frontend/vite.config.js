// frontend/vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react' // 👈 Updated to point to the correct default plugin
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
})