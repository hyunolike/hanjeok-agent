import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { buildSync } from 'esbuild'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const source = join(root, '.cloudflare/output/v1/workers/default')
const output = join(root, '.cloudflare/pages')
if (!existsSync(join(source, 'bundle/index.js')) || !existsSync(join(source, 'assets'))) {
  throw new Error('Cloudflare build missing. Run pnpm build:vinext first.')
}
const config = JSON.parse(readFileSync(join(source, 'worker.config.json'), 'utf8'))
if (Object.keys(config.env ?? {}).some(key => key !== 'ASSETS')) {
  throw new Error('Pages packaging only supports the ASSETS binding. Configure new bindings explicitly.')
}

rmSync(output, { recursive: true, force: true })
mkdirSync(output, { recursive: true })
for (const entry of readdirSync(join(source, 'assets'))) {
  // Build metadata stays private; only public files go to Pages Static Assets.
  if (entry.startsWith('.') || entry === 'vinext-client-entry-manifest.json') continue
  cpSync(join(source, 'assets', entry), join(output, entry), { recursive: true })
}
// A single ESM entry avoids Wrangler's Pages middleware rewriting the native
// module graph (SSR contains a cycle back to ../index.js).
buildSync({
  entryPoints: [join(source, 'bundle/index.js')],
  bundle: true,
  format: 'esm',
  platform: 'neutral',
  target: 'es2022',
  external: ['cloudflare:*', 'node:*'],
  outfile: join(output, '_worker.js'),
  minify: true,
})
writeFileSync(join(output, '_routes.json'), JSON.stringify({
  version: 1,
  include: ['/*'],
  exclude: ['/_next/static/*', '/*/_next/static/*', '/brand/*'],
}, null, 2) + '\n')
console.log('Prepared .cloudflare/pages with an ESM Worker and static assets.')
