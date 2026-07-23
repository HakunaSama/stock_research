import { useEffect, useRef } from "react";
import { animate, useInView } from "framer-motion";

interface Props {
  value: number;
  digits?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  duration?: number;
}

// 数字滚动：入场时从 0 递增到目标值。
export default function AnimatedNumber({
  value,
  digits = 0,
  prefix = "",
  suffix = "",
  className,
  duration = 1.1,
}: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-10% 0px" });

  useEffect(() => {
    if (!inView) return;
    const node = ref.current;
    if (!node) return;
    const controls = animate(0, value, {
      duration,
      ease: [0.16, 1, 0.3, 1],
      onUpdate(latest) {
        node.textContent = `${prefix}${latest.toFixed(digits)}${suffix}`;
      },
    });
    return () => controls.stop();
  }, [inView, value, digits, prefix, suffix, duration]);

  return (
    <span ref={ref} className={className}>
      {prefix}
      {(0).toFixed(digits)}
      {suffix}
    </span>
  );
}
