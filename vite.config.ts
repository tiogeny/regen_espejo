import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  base: './', // Permite que funcione en GitHub Pages (ej. /regen_espejo/)
  plugins: [
    react(),
    tailwindcss(),
  ],
})
