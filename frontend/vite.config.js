import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
export default defineConfig(function (_a) {
    var mode = _a.mode;
    var env = loadEnv(mode, fileURLToPath(new URL('.', import.meta.url)), '');
    var apiTarget = env.VITE_DEV_API_TARGET || 'http://127.0.0.1:8000';
    return {
        plugins: [react()],
        server: {
            host: '0.0.0.0',
            port: 5173,
            proxy: {
                '/api': {
                    target: apiTarget,
                    changeOrigin: true,
                },
            },
        },
        preview: {
            host: '0.0.0.0',
            port: 4173,
        },
        build: {
            outDir: 'dist',
            emptyOutDir: true,
        },
    };
});
