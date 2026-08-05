import { useCallback, useEffect, useRef, useState } from "react";

type Direction = "horizontal" | "vertical";

interface ResizableSplitProps {
  direction: Direction;
  first: React.ReactNode;
  second: React.ReactNode;
  initialSize: number;
  minFirst: number;
  minSecond: number;
  storageKey: string;
  className?: string;
  firstLabel: string;
  secondLabel: string;
}

const HANDLE_SIZE = 10;

function savedSize(key: string, fallback: number) {
  const value = Number(window.localStorage.getItem(key));
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

export default function ResizableSplit({
  direction,
  first,
  second,
  initialSize,
  minFirst,
  minSecond,
  storageKey,
  className = "",
  firstLabel,
  secondLabel,
}: ResizableSplitProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ pointer: number; size: number } | null>(null);
  const [size, setSize] = useState(() => savedSize(storageKey, initialSize));
  const [dragging, setDragging] = useState(false);

  const clamp = useCallback((next: number) => {
    const rect = containerRef.current?.getBoundingClientRect();
    const total = rect ? (direction === "horizontal" ? rect.width : rect.height) : Infinity;
    return Math.round(Math.max(minFirst, Math.min(next, total - minSecond - HANDLE_SIZE)));
  }, [direction, minFirst, minSecond]);

  const commit = useCallback((next: number) => {
    const value = clamp(next);
    setSize(value);
    window.localStorage.setItem(storageKey, String(value));
  }, [clamp, storageKey]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(() => setSize((current) => clamp(current)));
    observer.observe(container);
    return () => observer.disconnect();
  }, [clamp]);

  useEffect(() => {
    const move = (event: PointerEvent) => {
      if (!dragRef.current) return;
      const pointer = direction === "horizontal" ? event.clientX : event.clientY;
      setSize(clamp(dragRef.current.size + pointer - dragRef.current.pointer));
    };
    const end = () => {
      if (!dragRef.current) return;
      dragRef.current = null;
      setDragging(false);
      setSize((current) => {
        const next = clamp(current);
        window.localStorage.setItem(storageKey, String(next));
        return next;
      });
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
      window.removeEventListener("pointercancel", end);
    };
  }, [clamp, direction, storageKey]);

  const template = `${size}px ${HANDLE_SIZE}px minmax(0, 1fr)`;
  return (
    <div
      ref={containerRef}
      className={`resizable-split ${dragging ? "is-resizing" : ""} ${className}`}
      data-direction={direction}
      style={direction === "horizontal" ? { gridTemplateColumns: template } : { gridTemplateRows: template }}
    >
      <section className="min-h-0 min-w-0 overflow-hidden" aria-label={firstLabel}>{first}</section>
      <div
        role="separator"
        tabIndex={0}
        aria-label={`调整${firstLabel}与${secondLabel}大小`}
        aria-orientation={direction === "horizontal" ? "vertical" : "horizontal"}
        aria-valuemin={minFirst}
        aria-valuenow={size}
        className="resize-handle"
        onPointerDown={(event) => {
          event.preventDefault();
          dragRef.current = {
            pointer: direction === "horizontal" ? event.clientX : event.clientY,
            size,
          };
          setDragging(true);
        }}
        onDoubleClick={() => commit(initialSize)}
        onKeyDown={(event) => {
          const backward = direction === "horizontal" ? event.key === "ArrowLeft" : event.key === "ArrowUp";
          const forward = direction === "horizontal" ? event.key === "ArrowRight" : event.key === "ArrowDown";
          if (!backward && !forward && event.key !== "Home") return;
          event.preventDefault();
          commit(event.key === "Home" ? initialSize : size + (forward ? 24 : -24));
        }}
      >
        <span />
      </div>
      <section className="min-h-0 min-w-0 overflow-hidden" aria-label={secondLabel}>{second}</section>
    </div>
  );
}
