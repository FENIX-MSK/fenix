import {
  bindThemeParamsCssVars,
  hideBackButton,
  init,
  isThemeParamsDark,
  miniAppReady,
  mountBackButton,
  mountMiniAppSync,
  mountThemeParamsSync,
  onBackButtonClick,
  openLink,
  retrieveLaunchParams,
  retrieveRawInitData,
  setMiniAppBackgroundColor,
  setMiniAppHeaderColor,
  showBackButton,
} from '@telegram-apps/sdk'

import { mockTelegramClientInDev } from './devTelegramMock'
import type { Platform, PlatformUser } from './types'

type Hex = `#${string}`

export const telegramPlatform: Platform = {
  name: 'telegram',
  hasNativeBackButton: true,

  init() {
    if (import.meta.env.DEV) mockTelegramClientInDev()
    init()
    // Expose the user's Telegram theme as --tg-theme-* CSS variables.
    if (mountThemeParamsSync.isAvailable()) {
      mountThemeParamsSync()
      bindThemeParamsCssVars()
    }
    if (mountMiniAppSync.isAvailable()) mountMiniAppSync()
    if (mountBackButton.isAvailable()) mountBackButton()
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

  isDark: () => isThemeParamsDark() ?? false,

  setColors(background) {
    const color = background as Hex
    if (setMiniAppHeaderColor.isAvailable()) setMiniAppHeaderColor(color)
    if (setMiniAppBackgroundColor.isAvailable()) setMiniAppBackgroundColor(color)
  },

  showBackButton(onBack) {
    if (!showBackButton.isAvailable()) return () => {}
    showBackButton()
    const off = onBackButtonClick(onBack)
    return () => {
      off()
      hideBackButton()
    }
  },

  openLink(url) {
    if (openLink.isAvailable()) openLink(url)
    else window.open(url, '_blank', 'noopener')
  },
}
