import type { Platform } from './types'

/** Plain browser outside a messenger: local UI work only, the backend rejects it. */
export const browserPlatform: Platform = {
  name: 'browser',
  hasNativeBackButton: false,
  hasNativeMainButton: false,
  showMainButton: () => () => {},
  init() {},
  getUser: () => null,
  getInitDataRaw: () => null,
  isDark: () => window.matchMedia('(prefers-color-scheme: dark)').matches,
  setColors() {},
  // The browser's own back is the fallback; screens also offer an in-page back link.
  showBackButton: () => () => {},
  haptic() {},
  requestContact: async () => null,
  openTelegramLink(url) {
    window.open(url, '_blank', 'noopener')
  },
  openLink(url) {
    window.open(url, '_blank', 'noopener')
  },
}
