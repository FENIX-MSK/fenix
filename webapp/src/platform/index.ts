import { isTMA } from '@telegram-apps/sdk'

import { browserPlatform } from './browser'
import { telegramPlatform } from './telegram'
import type { Platform } from './types'

export type { Platform, PlatformUser } from './types'

function detectPlatform(): Platform {
  if (isTMA()) return telegramPlatform
  return browserPlatform
}

export const platform: Platform = detectPlatform()
