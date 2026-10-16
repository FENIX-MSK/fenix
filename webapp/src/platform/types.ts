export type PlatformName = 'telegram' | 'browser'

export interface PlatformUser {
  id: number
  firstName: string
  lastName?: string
  username?: string
}

/**
 * Everything the app needs from the host messenger.
 * Telegram today; MAX later gets its own implementation of the same interface.
 */
export interface Platform {
  readonly name: PlatformName
  init(): void
  getUser(): PlatformUser | null
  /** Signed launch data the backend validates; null outside a messenger. */
  getInitDataRaw(): string | null
}
