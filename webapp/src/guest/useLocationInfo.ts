import { api } from '../api/client'
import type { LocationInfo } from '../api/types'
import { type Remote, useRemote } from './useRemote'

export type LocationState = Remote<LocationInfo>

const loadLocation = () => api.GET('/api/v1/location')

export function useLocationInfo() {
  return useRemote(loadLocation)
}
