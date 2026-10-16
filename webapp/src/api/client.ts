import { platform } from '../platform'

export async function apiGet<T>(path: string): Promise<T> {
  const headers: HeadersInit = {}
  const initData = platform.getInitDataRaw()
  if (initData) headers.Authorization = `tma ${initData}`

  const response = await fetch(`/api${path}`, { headers })
  if (!response.ok) throw new Error(`GET ${path} failed: ${response.status}`)
  return (await response.json()) as T
}
