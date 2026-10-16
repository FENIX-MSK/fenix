import type { components } from './schema'

/** Response shapes from the generated OpenAPI schema; never written by hand. */
export type Schemas = components['schemas']
export type LocationInfo = Schemas['LocationOut']
export type Menu = Schemas['MenuOut']
export type MenuCategory = Schemas['MenuCategoryOut']
export type MenuDish = Schemas['MenuDishOut']
export type DishDetail = Schemas['DishOut']
export type ModifierGroup = Schemas['ModifierGroupOut']
export type PriceResult = Schemas['PriceOut']
export type Me = Schemas['Me']
export type Invitation = Schemas['InvitationOut']
export type StaffMember = Schemas['StaffMemberOut']
