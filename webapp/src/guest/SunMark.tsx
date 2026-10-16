/** The phoenix-sun rays from the printed menu; decorative only. */
export function SunMark({ size = 28 }: { size?: number }) {
  const rays = [-80, -60, -40, -20, 0, 20, 40, 60, 80]
  return (
    <svg width={size} height={size / 2 + 2} viewBox="0 0 40 22" aria-hidden="true" focusable="false">
      <g stroke="var(--gold)" strokeWidth="1.2" strokeLinecap="round">
        {rays.map((angle) => (
          <line key={angle} x1="20" y1="20" x2="20" y2={angle % 40 === 0 ? 2 : 7} transform={`rotate(${angle} 20 20)`} />
        ))}
      </g>
      <path d="M12 20 a8 8 0 0 1 16 0" fill="none" stroke="var(--gold)" strokeWidth="1.4" />
    </svg>
  )
}
