const RING_COUNT = 10;

const RISK_COLOR = {
  LOW: "#5FAE86",
  MEDIUM: "#D4A54A",
  HIGH: "#C1584B",
};

/**
 * Renders the application score as a set of concentric contour rings, the
 * way an elevation survey map represents rising ground -- rings up to the
 * score's "elevation" are filled in, rings above it stay as faint outlines.
 * This is the platform's signature visual: a scoring gauge literally drawn
 * as a topographic map, tying the UI back to the Directorate's own domain.
 */
export default function ScoreGauge({ score = 0, riskLevel = "LOW", size = 148 }) {
  const color = RISK_COLOR[riskLevel] || RISK_COLOR.LOW;
  const center = size / 2;
  const maxRadius = size / 2 - 6;
  const minRadius = maxRadius * 0.32;
  const filledRings = Math.round((score / 100) * RING_COUNT);

  const rings = Array.from({ length: RING_COUNT }, (_, i) => {
    const radius = minRadius + ((maxRadius - minRadius) * i) / (RING_COUNT - 1);
    const isFilled = i < filledRings;
    return { radius, isFilled };
  });

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {rings.map((ring, i) => (
          <circle
            key={i}
            cx={center}
            cy={center}
            r={ring.radius}
            fill="none"
            stroke={ring.isFilled ? color : "#24413A"}
            strokeOpacity={ring.isFilled ? 0.85 - i * 0.03 : 0.6}
            strokeWidth={ring.isFilled ? 1.6 : 1}
            strokeDasharray={ring.isFilled ? undefined : "2 3"}
          />
        ))}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display text-2xl font-semibold tabular-nums" style={{ color }}>
          {Math.round(score)}
        </span>
        <span className="font-mono text-[9px] tracking-widest text-ink_text-faint uppercase">/ 100</span>
      </div>
    </div>
  );
}
