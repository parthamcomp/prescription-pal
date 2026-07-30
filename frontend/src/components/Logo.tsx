interface LogoProps {
  size?: number;
  className?: string;
}

export default function Logo({ size = 36, className }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="Prescription Pal"
      className={className}
    >
      <rect width="64" height="64" rx="20" fill="#5B4BE6" />
      <text
        x="32"
        y="44"
        textAnchor="middle"
        fontFamily="'Plus Jakarta Sans', sans-serif"
        fontSize="32"
        fontWeight="800"
        fill="#FFFFFF"
      >
        Rx
      </text>
      <circle cx="50" cy="15" r="7" fill="#FFB43F" />
    </svg>
  );
}
