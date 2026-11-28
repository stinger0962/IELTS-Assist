// Opt-in local development server. Does not load Vite config or dotenv files.
import { fileURLToPath } from 'node:url';
import path from 'node:path';

export const localOptions = {
  root: fileURLToPath(new URL('../', import.meta.url)),
  configFile: false,
  envDir: false,
  envPrefix: [],
  define: { 'import.meta.env.VITE_API_URL': JSON.stringify('/api') },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    open: false,
    proxy: { '/api': { target: 'http://127.0.0.1:8001', changeOrigin: true } },
  },
};

export async function startLocal({ createServer, react }, args = process.argv.slice(2)) {
  if (args.length) throw new Error('Local sandbox accepts no server overrides');
  const server = await createServer({ ...localOptions, plugins: [react()] });
  await server.listen();
  return server;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.length !== 2) throw new Error('Local sandbox accepts no server overrides');
  const { createServer } = await import('vite');
  const { default: react } = await import('@vitejs/plugin-react');
  const server = await startLocal({ createServer, react });
  server.printUrls();
}
