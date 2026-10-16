import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import './index.css'
import { platform } from './platform'

try {
  platform.init()
} catch (error) {
  // A messenger bridge failure must not blank the app: the menu still works without it.
  console.error('platform.init failed', error)
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
