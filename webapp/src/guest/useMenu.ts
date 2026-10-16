import { api } from '../api/client'
import type { Menu } from '../api/types'
import { type Remote, useRemote } from './useRemote'

export type MenuState = Remote<Menu>

const loadMenu = () => api.GET('/api/v1/menu')

export function useMenu() {
  return useRemote(loadMenu)
}
