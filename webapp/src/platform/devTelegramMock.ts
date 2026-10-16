import { mockTelegramEnv, retrieveRawLaunchParams } from '@telegram-apps/sdk'

/**
 * Development only: a page opened at a `#tgWebAppData=…` URL in a plain browser tab has
 * launch data but no Telegram client to talk to. Mock the client so the SDK works the same
 * way as inside Telegram; method calls are logged instead of sent.
 */
export function mockTelegramClientInDev(): void {
  const insideClient = 'TelegramWebviewProxy' in window || window.parent !== window
  if (insideClient) return
  mockTelegramEnv({
    launchParams: retrieveRawLaunchParams(),
    onEvent([method, params]) {
      console.debug('[telegram mock]', method, params)
    },
  })
}
