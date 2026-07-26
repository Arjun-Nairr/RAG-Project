// Small self-contained gradient logo mark (a "spark" = insight). Brand colors
// are intentionally fixed across light/dark so the mark stays recognizable.
function BrandMark({ size = 26 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect width="24" height="24" rx="7" fill="url(#brand-grad)" />
      <path
        d="M12 5.5l1.7 3.6 3.8.4-2.9 2.5.9 3.7-3.5-2-3.5 2 .9-3.7-2.9-2.5 3.8-.4z"
        fill="#fff"
      />
      <defs>
        <linearGradient id="brand-grad" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
          <stop stopColor="#c084fc" />
          <stop offset="1" stopColor="#7c3aed" />
        </linearGradient>
      </defs>
    </svg>
  )
}

export default BrandMark
