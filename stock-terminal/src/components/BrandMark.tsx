/** 知势 Cheese 品牌标 —— 芝士楔形图标 + 可选中英文名。 */
export function CheeseIcon({ size = 28, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden
    >
      <rect width="32" height="32" rx="8" fill="#F6C344" />
      <path d="M6 22.5L16 6.5L26 22.5H6Z" fill="#F8D56B" />
      <path
        d="M6 22.5H26L21.2 25.2C19.1 26.4 16.9 26.4 14.8 25.2L6 22.5Z"
        fill="#E8A91A"
      />
      <path d="M6 22.5L16 6.5L18.2 10.2L6 22.5Z" fill="#F0B92A" opacity="0.55" />
      <circle cx="13.2" cy="16.8" r="1.55" fill="#D4920F" />
      <circle cx="18.6" cy="18.4" r="2.05" fill="#D4920F" />
      <circle cx="15.8" cy="21.6" r="1.15" fill="#D4920F" />
      <circle cx="20.8" cy="14.2" r="1.05" fill="#D4920F" />
    </svg>
  );
}

export default function BrandMark({
  size = "md",
  showSubtitle = true,
}: {
  size?: "sm" | "md" | "lg";
  showSubtitle?: boolean;
}) {
  const icon = size === "lg" ? 36 : size === "sm" ? 26 : 32;
  const title =
    size === "lg" ? "text-lg" : size === "sm" ? "text-[13px]" : "text-[14px]";
  return (
    <div className="flex items-center gap-2.5">
      <CheeseIcon size={icon} className="shrink-0 shadow-sm" />
      <div className="min-w-0">
        <div className={`font-display font-bold tracking-wide text-ink ${title}`}>知势</div>
        {showSubtitle && (
          <div className="text-2xs uppercase tracking-[0.22em] text-ink-3">Cheese</div>
        )}
      </div>
    </div>
  );
}
