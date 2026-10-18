// Reads official search results, never the view-counting place detail endpoint.
import { readFile, writeFile } from 'node:fs/promises'
const ids = ['129efdef-41ec-4044-ac87-303abe4ccdde', 'e66302c6-b413-4a07-88a5-3bd55e61fc2a', '5a2eb601-1f2b-499b-83eb-8a0093f4817e', 'dfdb93f6-bfc3-478d-8a14-f9fde88e9c2a']
const places = new Map()
for (const uuid of ids) {
  const snapshot = JSON.parse(await readFile(new URL(`../frontend/src/lib/recorded-courses/${uuid}.json`, import.meta.url)))
  for (const place of snapshot.course.items) places.set(place.attractionId, place)
}
const records = []
for (const place of places.values()) {
  const keyword = place.name.split(' [')[0]
  const sourceUrl = `https://api.hanjeok.com/api/v1/attractions/search?keyword=${encodeURIComponent(keyword)}`
  const response = await fetch(sourceUrl, { signal: AbortSignal.timeout(15000) })
  if (!response.ok) throw new Error(`Search ${place.attractionId}: HTTP ${response.status}`)
  const body = await response.json()
  const exact = body.data?.find(item => item.id === place.attractionId)
  if (!exact || exact.name !== place.name || !exact.areaLabel.startsWith('서울 ') || !place.imageUrls.includes(exact.imageUrl)) throw new Error(`Place mismatch: ${place.attractionId}`)
  records.push({ ...exact, sourceUrl, capturedAt: new Date().toISOString() })
  console.log(exact.id, exact.name, exact.areaLabel)
}
await writeFile(new URL('../frontend/src/lib/recorded-places.json', import.meta.url), JSON.stringify(records, null, 2) + '\n')
