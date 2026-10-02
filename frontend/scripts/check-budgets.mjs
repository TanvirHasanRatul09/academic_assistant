import { readdir, stat } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const dist = new URL('../dist/', import.meta.url)
const assets = new URL('./assets/', dist)
const assetsPath = fileURLToPath(assets)
const limits = {
  entryJavaScript: 320 * 1024,
  routeJavaScript: 25 * 1024,
  stylesheet: 65 * 1024,
}
const files = await readdir(assets)
const measurements = []
for (const file of files) {
  const bytes = (await stat(join(assetsPath, file))).size
  measurements.push({ file, bytes })
}
const javascript = measurements.filter(({ file }) => file.endsWith('.js'))
const styles = measurements.filter(({ file }) => file.endsWith('.css'))
const entry = javascript.find(({ file }) => file.startsWith('index-'))
const failures = []
if (!entry || entry.bytes > limits.entryJavaScript) failures.push('Initial JavaScript exceeds 320 KiB')
for (const asset of javascript.filter(({ file }) => !file.startsWith('index-') && !file.startsWith('workbox-'))) {
  if (asset.bytes > limits.routeJavaScript) failures.push(asset.file + ' exceeds the 25 KiB route budget')
}
for (const asset of styles) if (asset.bytes > limits.stylesheet) failures.push(asset.file + ' exceeds the 65 KiB CSS budget')
if (javascript.some(({ file }) => /three|webgl/i.test(file))) failures.push('Decorative 3D code entered the production assets')
console.log(JSON.stringify({ limits, measurements }, null, 2))
if (failures.length) {
  console.error(failures.join(String.fromCharCode(10)))
  process.exit(1)
}

