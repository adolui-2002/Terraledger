/**
 * Ambient contour-line texture, echoing a topographic survey map. Used
 * sparingly behind hero panels only -- the signature motif should stay
 * quiet everywhere else in the interface.
 */
export default function ContourBackground({ className = "" }) {
  return (
    <svg
      className={`pointer-events-none absolute inset-0 h-full w-full opacity-[0.35] ${className}`}
      preserveAspectRatio="none"
      viewBox="0 0 800 300"
      fill="none"
    >
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <path
          key={i}
          d={`M -20 ${230 - i * 28} C 150 ${180 - i * 26}, 280 ${300 - i * 30}, 430 ${210 - i * 24} S 700 ${140 - i * 20}, 850 ${220 - i * 26}`}
          stroke="#D4A54A"
          strokeOpacity={0.12 - i * 0.012}
          strokeWidth="1"
          fill="none"
        />
      ))}
    </svg>
  );
}
