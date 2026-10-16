// Server error codes → what the staff member should do (EXPERIENCE.md › Voice and Tone).
const MESSAGES: Record<string, string> = {
  name_required: 'Укажите название',
  dish_needs_size: 'У блюда должен быть хотя бы один размер',
  size_name_required: 'Назовите каждый размер, если их несколько',
  duplicate_size_name: 'Названия размеров не должны повторяться',
  category_not_empty: 'Сначала перенесите или удалите блюда этой категории',
  choice_bounds: 'Минимум не больше максимума, максимум — от 1 до числа опций',
  group_needs_option: 'Добавьте хотя бы одну опцию',
  duplicate_option_name: 'Названия опций не должны повторяться',
}

export function saveErrorText(code: string | undefined): string {
  return (code && MESSAGES[code]) || 'Не сохранилось, попробуйте ещё раз'
}

/** Run an API call; resolve to null on success or to the error text. */
export async function attempt(call: () => Promise<{ error?: { error: { code: string } } }>): Promise<string | null> {
  try {
    const { error } = await call()
    return error ? saveErrorText(error.error.code) : null
  } catch {
    return saveErrorText(undefined)
  }
}
