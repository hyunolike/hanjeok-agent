// Read-only capture of the four verified Seoul public, saved Hanjeok courses. No course is created.
import { mkdir, writeFile } from 'node:fs/promises'
const uuids = [
  '129efdef-41ec-4044-ac87-303abe4ccdde',
  'e66302c6-b413-4a07-88a5-3bd55e61fc2a',
  '5a2eb601-1f2b-499b-83eb-8a0093f4817e',
  'dfdb93f6-bfc3-478d-8a14-f9fde88e9c2a',
]
await mkdir(new URL('../frontend/src/lib/recorded-courses/', import.meta.url), { recursive: true })
for (const uuid of uuids) {
  const sourceUrl = `https://api.hanjeok.com/api/v1/courses/${uuid}`
  const response = await fetch(sourceUrl, { signal: AbortSignal.timeout(15000) })
  if (!response.ok) throw new Error(`${uuid}: HTTP ${response.status}`)
  const body = await response.json()
  if (!body.success || body.data.uuid !== uuid || !body.data.items.length) throw new Error(`Invalid course: ${uuid}`)
  // Preserve the official response, including order, saved grades, descriptions and image URLs.
  const snapshot = { sourceUrl, capturedAt: new Date().toISOString(), course: body.data }
  await writeFile(new URL(`../frontend/src/lib/recorded-courses/${uuid}.json`, import.meta.url), JSON.stringify(snapshot, null, 2) + '\n')
  console.log(uuid, body.data.targetDate, body.data.items.map(item => `${item.name} (${item.grade ?? 'no forecast'}; ${item.imageUrls.length} photos)`).join(' → '))
}
