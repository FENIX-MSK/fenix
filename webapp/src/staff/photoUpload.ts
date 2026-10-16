import { platform } from '../platform'

export const MAX_PHOTO_BYTES = 15 * 1024 * 1024

/** XHR rather than fetch: upload progress (EXPERIENCE.md › «Загрузка фото»). */
export function uploadPhoto(url: string, file: File, onProgress: (share: number) => void): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', url)
    const initData = platform.getInitDataRaw()
    if (initData) request.setRequestHeader('Authorization', `tma ${initData}`)
    request.upload.onprogress = (event) => event.lengthComputable && onProgress(event.loaded / event.total)
    request.onload = () => {
      const body = JSON.parse(request.responseText || 'null')
      if (request.status === 200) resolve(body)
      else reject(new Error(body?.error?.code ?? 'failed'))
    }
    request.onerror = () => reject(new Error('network'))
    const form = new FormData()
    form.append('file', file)
    request.send(form)
  })
}

export const PHOTO_MESSAGES: Record<string, string> = {
  unsupported_image: 'Нужна фотография JPEG, PNG, WebP или HEIC',
  image_too_large: 'Фото больше 15 МБ',
}

