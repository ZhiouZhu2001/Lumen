type IconProps = {direction?: "left" | "right"};

export function ArrowIcon({direction = "right"}: IconProps) {
  return <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={`icon ${direction === "left" ? "icon-back" : ""}`}><path d="M4 12h16m-6-6 6 6-6 6" /></svg>;
}

export function ChevronIcon() {
  return <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="icon chevron"><path d="m6 9 6 6 6-6" /></svg>;
}

export function CopyIcon() {
  return <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="icon"><rect x="8" y="8" width="12" height="13" rx="1" /><path d="M16 4H5a1 1 0 0 0-1 1v12" /></svg>;
}
