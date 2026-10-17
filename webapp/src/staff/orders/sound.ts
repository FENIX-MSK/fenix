/**
 * The new-order chime. Browsers only allow audio after a user gesture, so the board asks
 * for one tap to enable it (EXPERIENCE.md › Sound). Generated, so there is no asset to load.
 */
let context: AudioContext | null = null

export function soundEnabled(): boolean {
  return context?.state === 'running'
}

export async function enableSound(): Promise<boolean> {
  try {
    context ??= new AudioContext()
    if (context.state !== 'running') await context.resume()
    return context.state === 'running'
  } catch {
    return false
  }
}

export function chime(): void {
  if (!context || context.state !== 'running') return
  const start = context.currentTime
  ;[880, 1320].forEach((frequency, index) => {
    const oscillator = context!.createOscillator()
    const gain = context!.createGain()
    const at = start + index * 0.18
    oscillator.frequency.value = frequency
    oscillator.type = 'sine'
    gain.gain.setValueAtTime(0.0001, at)
    gain.gain.exponentialRampToValueAtTime(0.4, at + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.35)
    oscillator.connect(gain).connect(context!.destination)
    oscillator.start(at)
    oscillator.stop(at + 0.4)
  })
}
