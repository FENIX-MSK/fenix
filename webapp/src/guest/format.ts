const rubles = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })

/** Display only: the price itself always comes from the server (AD-6). */
export function formatPrice(kopecks: number, from = false): string {
  return `${from ? 'от ' : ''}${rubles.format(kopecks / 100)} ₽`
}
