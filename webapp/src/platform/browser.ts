import type { Platform } from './types'

/** Plain browser outside a messenger: local UI work only, the backend rejects it. */
export const browserPlatform: Platform = {
  name: 'browser',
  init() {},
  getUser: () => null,
  getInitDataRaw: () => null,
}
