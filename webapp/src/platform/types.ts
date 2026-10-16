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
export interface MainButtonParams {
  text: string
  enabled: boolean
  loading: boolean
  color: string
  textColor: string
  onClick: () => void
}

export interface Platform {
  readonly name: PlatformName
  init(): void
  getUser(): PlatformUser | null
  /** Signed launch data the backend validates; null outside a messenger. */
  getInitDataRaw(): string | null
  /** The messenger's color scheme (the system one in a browser). */
  isDark(): boolean
  /** Paint the messenger's header and background to match the screen. */
  setColors(background: string): void
  /** Whether the messenger draws the main action button; otherwise screens show their own. */
  readonly hasNativeMainButton: boolean
  /** Show the native main button (EXPERIENCE.md › «Основное действие»); returns hide. */
  showMainButton(params: MainButtonParams): () => void
  /** Whether the messenger draws its own back button; otherwise screens show one. */
  readonly hasNativeBackButton: boolean
  /** Show the native back button; the returned function hides it again. */
  showBackButton(onBack: () => void): () => void
  /** Short vibration: a choice made, a rejected action, a completed action. */
  haptic(kind: 'selection' | 'error' | 'success'): void
  /** Telegram's «Поделиться контактом»: the signed response, or null if unavailable/denied. */
  requestContact(): Promise<string | null>
  /** Open a t.me link inside Telegram (share sheet, chats, bots). */
  openTelegramLink(url: string): void
  /** Open an external link (maps, social networks) outside the Mini App. */
  openLink(url: string): void
}
