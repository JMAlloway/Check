import { useCallback, useEffect, useRef, useState } from 'react';

interface ResizableWidthOptions {
  storageKey: string;
  defaultWidth: number;
  min: number;
  max: number;
}

/**
 * Drag-to-resize width for a left-hand panel.
 *
 * Returns the current width (persisted to localStorage), a ref to put on the
 * grid/flex container that the width is measured against, and an onMouseDown
 * handler to attach to a resize handle. The width is clamped to [min, max] and
 * derived from the pointer's x-offset within the container, so the rest of the
 * layout (which should flex to fill the remaining space) reacts automatically.
 */
export function useResizableWidth({ storageKey, defaultWidth, min, max }: ResizableWidthOptions) {
  const [width, setWidth] = useState<number>(() => {
    const stored = typeof window !== 'undefined' ? window.localStorage.getItem(storageKey) : null;
    const parsed = stored ? parseInt(stored, 10) : NaN;
    return Number.isFinite(parsed) ? Math.min(max, Math.max(min, parsed)) : defaultWidth;
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    draggingRef.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!draggingRef.current || !containerRef.current) return;
      const left = containerRef.current.getBoundingClientRect().left;
      const next = Math.min(max, Math.max(min, Math.round(e.clientX - left)));
      setWidth(next);
    };
    const onUp = () => {
      if (!draggingRef.current) return;
      draggingRef.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      try {
        window.localStorage.setItem(storageKey, String(width));
      } catch {
        /* ignore persistence failures (e.g. private mode) */
      }
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [storageKey, width, min, max]);

  return { width, containerRef, onMouseDown };
}
