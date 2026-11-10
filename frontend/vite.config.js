import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The backend allows http://localhost:5173 by default (CORS_ORIGINS), so keep this port.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  preview: { port: 5173, strictPort: true },
});
