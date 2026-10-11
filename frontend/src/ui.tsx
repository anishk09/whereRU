import type { ReactNode } from "react";

export type IconName =
  | "home"
  | "camera"
  | "bag"
  | "user"
  | "arrow"
  | "chevron"
  | "check"
  | "clock"
  | "bell"
  | "shield"
  | "map"
  | "search"
  | "moon"
  | "settings"
  | "logout"
  | "lock"
  | "x"
  | "plus"
  | "sparkles"
  | "image"
  | "refresh"
  | "locate"
  | "door";

const paths: Record<IconName, ReactNode> = {
  home: <><path d="m3 11 9-8 9 8" /><path d="M5 10v10h14V10M9 20v-6h6v6" /></>,
  camera: <><path d="M4 7h3l1.5-2h7L17 7h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z" /><circle cx="12" cy="13" r="4" /></>,
  bag: <><path d="M5 8h14l-1 13H6L5 8Z" /><path d="M9 9V6a3 3 0 0 1 6 0v3" /></>,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  arrow: <><path d="m15 18-6-6 6-6" /></>,
  chevron: <path d="m9 18 6-6-6-6" />,
  check: <path d="m5 12 4 4L19 6" />,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
  shield: <><path d="M12 3 4 6v6c0 5 3.4 8.3 8 10 4.6-1.7 8-5 8-10V6l-8-3Z" /><path d="m9 12 2 2 4-4" /></>,
  map: <><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z" /><path d="M9 3v15M15 6v15" /></>,
  search: <><circle cx="10.5" cy="10.5" r="7" /><path d="m16 16 5 5" /></>,
  moon: <path d="M20 15.5A8.5 8.5 0 0 1 8.5 4 8.5 8.5 0 1 0 20 15.5Z" />,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a2 2 0 0 0 .4 2.2l.1.1-2.6 2.6-.1-.1a2 2 0 0 0-2.2-.4 2 2 0 0 0-1.2 1.8V21h-3.6v-.2A2 2 0 0 0 9 19a2 2 0 0 0-2.2.4l-.1.1-2.6-2.6.1-.1a2 2 0 0 0 .4-2.2A2 2 0 0 0 2.8 13H3V9.4h-.2A2 2 0 0 0 4.6 8a2 2 0 0 0-.4-2.2l-.1-.1 2.6-2.6.1.1A2 2 0 0 0 9 3.6 2 2 0 0 0 10.2 2h3.6A2 2 0 0 0 15 3.6a2 2 0 0 0 2.2-.4l.1-.1 2.6 2.6-.1.1a2 2 0 0 0-.4 2.2 2 2 0 0 0 1.8 1.2h.2V13h-.2a2 2 0 0 0-1.8 2Z" /></>,
  logout: <><path d="M10 17l5-5-5-5M15 12H3" /><path d="M14 3h7v18h-7" /></>,
  lock: <><rect x="4" y="10" width="16" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" /></>,
  x: <><path d="m6 6 12 12M18 6 6 18" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  sparkles: <><path d="m12 3 1.3 3.7L17 8l-3.7 1.3L12 13l-1.3-3.7L7 8l3.7-1.3L12 3Z" /><path d="m19 14 .7 2.3L22 17l-2.3.7L19 20l-.7-2.3L16 17l2.3-.7L19 14ZM5 13l.7 2.3L8 16l-2.3.7L5 19l-.7-2.3L2 16l2.3-.7L5 13Z" /></>,
  image: <><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="9" cy="10" r="2" /><path d="m21 16-5-5-9 9" /></>,
  refresh: <><path d="M20 11a8 8 0 0 0-14.6-4.5L4 8" /><path d="M4 3v5h5" /><path d="M4 13a8 8 0 0 0 14.6 4.5L20 16" /><path d="M20 21v-5h-5" /></>,
  locate: <><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /><circle cx="12" cy="12" r="7" /></>,
  door: <><path d="M5 21V4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v17" /><path d="M3 21h18" /><circle cx="15" cy="12" r=".8" /></>,
};

export function Icon({ name, size = 22, className = "" }: { name: IconName; size?: number; className?: string }) {
  return <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{paths[name]}</svg>;
}

export function Wordmark({ size = "header", className = "" }: { size?: "welcome" | "header" | "notification"; className?: string }) {
  return <span className={`brand-wordmark brand-wordmark-${size} ${className}`} aria-label="Where RU?">
    <span className="brand-lockup" aria-hidden="true"><span className="brand-where">Where</span><span className="brand-ru"><span className="brand-r">R</span><span className="brand-u">U</span></span><span className="brand-question">?</span></span>
  </span>;
}

export function BrandIcon({ className = "" }: { className?: string }) {
  return <span className={`brand-icon ${className}`} aria-hidden="true">
    <svg viewBox="0 0 24 24" fill="none" focusable="false">
      <circle cx="10.25" cy="10.25" r="6.75" stroke="currentColor" strokeWidth="1.8" />
      <path d="m15.15 15.15 5.1 5.1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M8.25 8.2a2.1 2.1 0 0 1 4.1.65c0 1.55-1.85 1.75-1.85 3.15" stroke="currentColor" strokeWidth="1.55" strokeLinecap="round" />
      <circle cx="10.5" cy="14.3" r=".85" fill="currentColor" />
    </svg>
  </span>;
}

export function Button({ children, onClick, variant = "primary", disabled = false, className = "" }: { children: ReactNode; onClick?: () => void; variant?: "primary" | "secondary" | "ghost"; disabled?: boolean; className?: string }) {
  return <button type="button" className={`button button-${variant} ${className}`} onClick={onClick} disabled={disabled}>{children}</button>;
}
