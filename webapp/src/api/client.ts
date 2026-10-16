import createClient, { type Middleware } from 'openapi-fetch'

import { platform } from '../platform'
import type { paths } from './schema'

// Every request carries the messenger's signed launch data; the server verifies it.
const messengerAuth: Middleware = {
  onRequest({ request }) {
    const initData = platform.getInitDataRaw()
    if (initData) request.headers.set('Authorization', `tma ${initData}`)
    return request
  },
}

// Paths in the schema are absolute (/api/...), so requests go to the page's origin.
export const api = createClient<paths>()
api.use(messengerAuth)
