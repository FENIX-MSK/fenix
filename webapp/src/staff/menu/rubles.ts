/** Input conversion only — prices themselves are computed on the server (AD-6). */
export function rublesToKopecks(text: string): number | null {
  const normalized = text.replace(/\s/g, '').replace(',', '.')
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) return null
  return Math.round(Number(normalized) * 100)
}

export function kopecksToRubles(kopecks: number): string {
  return kopecks % 100 === 0 ? String(kopecks / 100) : (kopecks / 100).toFixed(2).replace('.', ',')
}
