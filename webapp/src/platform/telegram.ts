import {
  bindThemeParamsCssVars,
  hapticFeedbackNotificationOccurred,
  hapticFeedbackSelectionChanged,
  hideBackButton,
  init,
  isThemeParamsDark,
  miniAppReady,
  mountBackButton,
  mountMainButton,
  offMainButtonClick,
  onMainButtonClick,
  setMainButtonParams,
  mountMiniAppSync,
  mountThemeParamsSync,
  onBackButtonClick,
  openLink,
  openTelegramLink,
  requestContactComplete,
  retrieveLaunchParams,
  retrieveRawInitData,
  setMiniAppBackgroundColor,
  setMiniAppHeaderColor,
  showBackButton,
} from '@telegram-apps/sdk'

import { mockTelegramClientInDev } from './devTelegramMock'
import type { Platform, PlatformUser } from './types'

// A plain browser tab with mocked launch data has no Telegram UI to draw buttons in.
let mocked = false

type Hex = `#${string}`

export const telegramPlatform: Platform = {
  name: 'telegram',
  hasNativeBackButton: true,
  get hasNativeMainButton() {
    return !mocked && setMainButtonParams.isAvailable()
  },

  init() {
    if (import.meta.env.DEV) mocked = mockTelegramClientInDev()
    init()
    // Expose the user's Telegram theme as --tg-theme-* CSS variables.
    if (mountThemeParamsSync.isAvailable()) {
      mountThemeParamsSync()
      bindThemeParamsCssVars()
    }
    if (mountMiniAppSync.isAvailable()) mountMiniAppSync()
    if (mountBackButton.isAvailable()) mountBackButton()
    if (mountMainButton.isAvailable()) mountMainButton()
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

  showMainButton({ text, enabled, loading, color, textColor, onClick }) {
    if (!setMainButtonParams.isAvailable()) return () => {}
    setMainButtonParams({
      text,
      isVisible: true,
      isEnabled: enabled,
      isLoaderVisible: loading,
      backgroundColor: color as `#${string}`,
      textColor: textColor as `#${string}`,
    })
    onMainButtonClick(onClick)
    return () => {
      offMainButtonClick(onClick)
      setMainButtonParams({ isVisible: false, isLoaderVisible: false })
    }
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

  haptic(kind) {
    if (kind === 'selection') {
      if (hapticFeedbackSelectionChanged.isAvailable()) hapticFeedbackSelectionChanged()
    } else if (hapticFeedbackNotificationOccurred.isAvailable()) {
      hapticFeedbackNotificationOccurred(kind)
    }
  },

  async requestContact() {
    if (mocked || !requestContactComplete.isAvailable()) return null
    try {
      return (await requestContactComplete()).raw
    } catch {
      return null
    }
  },

  openTelegramLink(url) {
    if (openTelegramLink.isAvailable()) openTelegramLink(url)
    else window.open(url, '_blank', 'noopener')
  },

  openLink(url) {
    if (openLink.isAvailable()) openLink(url)
    else window.open(url, '_blank', 'noopener')
  },
}
