const P: Record<string, string> = {
  home: 'M3 11.5 12 4l9 7.5M5.5 10v9.5h13V10',
  pump: 'M4 9h9a4 4 0 0 1 4 4v1h3M4 9V6h6v3M7 14a3.5 3.5 0 1 0 7 0 3.5 3.5 0 0 0-7 0M17 14v4H9',
  bell: 'M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15L6 16ZM10 20.5a2 2 0 0 0 4 0',
  chart: 'M4 20V10m6 10V4m6 16v-7m5 7H3',
  plug: 'M9 3v5m6-5v5M6 8h12v3a6 6 0 0 1-12 0V8ZM12 17v4',
  printer: 'M7 9V4h10v5M7 17H5a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-2M7 14h10v6H7z',
  wrench: 'M14.5 6.5a4 4 0 0 0 5 5L11 20a2.1 2.1 0 0 1-3-3l8.5-8.5a4 4 0 0 0-2-2ZM7.5 17.5h.01',
  sensor: 'M3 12h3l2.5-6 4 12 2.5-6H21',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  alert: 'M12 4 2.8 19.5h18.4L12 4ZM12 10v4.5M12 17.2v.01',
  back: 'M15 5l-7 7 7 7',
  next: 'M9 5l7 7-7 7',
  clock: 'M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  shield: 'M12 3 5 6v5c0 5 3 8.5 7 10 4-1.5 7-5 7-10V6l-7-3ZM9 12l2.2 2.2L15.5 10',
  play: 'M7 5v14l12-7L7 5Z',
  pause: 'M8 5v14M16 5v14',
  flask: 'M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18l-5-9V3M8 15h8',
  eye: 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12ZM12 9.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5Z',
  list: 'M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01',
}

export default function Icon({ name, label }: { name: keyof typeof P | string; label?: string }) {
  return (
    <svg className="icon" viewBox="0 0 24 24" role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <path d={P[name] ?? P.alert} />
    </svg>
  )
}
