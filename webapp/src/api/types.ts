import type { components } from './schema'

/** Response shapes from the generated OpenAPI schema; never written by hand. */
export type Schemas = components['schemas']
export type LocationInfo = Schemas['LocationOut']
