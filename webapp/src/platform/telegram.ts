import {
  bindThemeParamsCssVars,
  init,
  miniAppReady,
  mountThemeParamsSync,
  retrieveLaunchParams,
  retrieveRawInitData,
} from '@telegram-apps/sdk'

import type { Platform, PlatformUser } from './types'

export const telegramPlatform: Platform = {
  name: 'telegram',

  init() {
    init()
    // Expose the user's Telegram theme as --tg-theme-* CSS variables.
    if (mountThemeParamsSync.isAvailable()) {
      mountThemeParamsSync()
      bindThemeParamsCssVars()
    }
    if (miniAppReady.isAvailable()) miniAppReady()
  },

  getUser(): PlatformUser | null {
    const user = retrieveLaunchParams(true).tgWebAppData?.user
    if (!user) return null
    return {
      id: user.id,
      firstName: user.firstName,
      lastName: user.lastName,
      username: user.username,
    }
  },

  getInitDataRaw: () => retrieveRawInitData() ?? null,
}
