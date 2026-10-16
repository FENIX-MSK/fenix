import { SunMark } from '../guest/SunMark'

export function Placeholder({ title, text }: { title: string; text: string }) {
  return (
    <>
      <h1 className="title staff-title">{title}</h1>
      <div className="empty">
        <SunMark size={40} />
        <p className="muted">{text}</p>
      </div>
    </>
  )
}
