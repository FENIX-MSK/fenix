import { api } from '../api/client'
import type { Me } from '../api/types'
import { type Remote, useRemote } from './useRemote'

export type MeState = Remote<Me>

const loadMe = () => api.GET('/api/v1/me')

export function useMe() {
  return useRemote(loadMe)
}
