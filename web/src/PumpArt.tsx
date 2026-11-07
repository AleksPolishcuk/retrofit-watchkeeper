/** A flat, original illustration of a motor-driven centrifugal pump for the headline. Decorative: hidden from assistive technology. */
export default function PumpArt({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 540 320" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="pa-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#4a86ff" />
          <stop offset=".55" stopColor="#2358d8" />
          <stop offset="1" stopColor="#133a9c" />
        </linearGradient>
        <linearGradient id="pa-case" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#5b95ff" />
          <stop offset=".6" stopColor="#2a62e6" />
          <stop offset="1" stopColor="#153fad" />
        </linearGradient>
        <linearGradient id="pa-steel" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#e3ecff" />
          <stop offset="1" stopColor="#9db8f0" />
        </linearGradient>
        <radialGradient id="pa-glow" cx=".5" cy=".5" r=".5">
          <stop offset="0" stopColor="#3b82ff" stopOpacity=".45" />
          <stop offset="1" stopColor="#3b82ff" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx="290" cy="170" rx="250" ry="140" fill="url(#pa-glow)" />
      <g fill="none" stroke="#7fa9ff" strokeOpacity=".35" strokeDasharray="5 6" strokeWidth="1.4">
        <circle cx="170" cy="165" r="128" />
        <path d="M20 290H520M170 20V300" />
      </g>
      {/* base */}
      <rect x="70" y="262" width="430" height="22" rx="8" fill="#0d2f7d" />
      <rect x="70" y="262" width="430" height="6" rx="3" fill="#3f78ee" opacity=".7" />
      {/* motor */}
      <rect x="262" y="118" width="226" height="132" rx="26" fill="url(#pa-body)" />
      {[286, 306, 326, 346, 366, 386, 406, 426].map((x) => <rect key={x} x={x} y="124" width="7" height="120" rx="3.5" fill="#0f347f" opacity=".55" />)}
      <rect x="262" y="118" width="226" height="14" rx="7" fill="#8cb6ff" opacity=".45" />
      <rect x="470" y="136" width="34" height="96" rx="12" fill="url(#pa-steel)" />
      <rect x="352" y="92" width="64" height="30" rx="8" fill="#1d4fc4" />
      <rect x="358" y="98" width="52" height="6" rx="3" fill="#8cb6ff" opacity=".6" />
      {/* coupling */}
      <rect x="236" y="168" width="34" height="34" rx="6" fill="url(#pa-steel)" />
      {/* discharge pipe */}
      <rect x="146" y="22" width="48" height="76" rx="6" fill="url(#pa-steel)" />
      <rect x="132" y="14" width="76" height="20" rx="8" fill="#cfe0ff" />
      {[142, 202].map((x) => <circle key={x} cx={x} cy="24" r="3.5" fill="#7a97d6" />)}
      {/* inlet pipe */}
      <rect x="24" y="143" width="84" height="46" rx="6" fill="url(#pa-steel)" />
      <rect x="14" y="128" width="26" height="76" rx="9" fill="#cfe0ff" />
      {[138, 194].map((y) => <circle key={y} cx="27" cy={y} r="3.5" fill="#7a97d6" />)}
      {/* volute casing */}
      <circle cx="170" cy="166" r="104" fill="url(#pa-case)" />
      <circle cx="170" cy="166" r="104" fill="none" stroke="#9cc0ff" strokeOpacity=".5" strokeWidth="3" />
      <circle cx="170" cy="166" r="80" fill="#1b4fc4" />
      {Array.from({ length: 12 }, (_, i) => {
        const a = (i / 12) * Math.PI * 2
        return <circle key={i} cx={170 + Math.cos(a) * 92} cy={166 + Math.sin(a) * 92} r="5.5" fill="#d6e5ff" stroke="#6c8fdc" strokeWidth="1.5" />
      })}
      <circle cx="170" cy="166" r="52" fill="url(#pa-steel)" />
      <circle cx="170" cy="166" r="34" fill="#143f9f" />
      <circle cx="170" cy="166" r="14" fill="#e3ecff" />
      <path d="M170 132a34 34 0 0 1 29 17" fill="none" stroke="#8cb6ff" strokeWidth="5" strokeLinecap="round" opacity=".8" />
    </svg>
  )
}
