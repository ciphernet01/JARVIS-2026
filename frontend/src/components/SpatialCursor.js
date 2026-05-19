import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';

const PINCH_GESTURES = new Set(['PINCH_HOLD', 'GESTURE_PINCH_HOLD']);
const PINCH_DWELL_MS = 140;
const INTERACTIVE_SELECTOR = [
  'button',
  'a[href]',
  'input',
  'select',
  'textarea',
  '[role="button"]',
  '[role="link"]',
  '[role="menuitem"]',
  '[data-spatial-interactive="true"]',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

function isInteractive(el, scopeRoot) {
  if (!el || !(el instanceof Element)) return false;
  if (el.closest('[data-spatial-cursor]')) return false;
  if (el.closest('[data-spatial-ignore="true"]')) return false;
  if (el.matches('[disabled], [aria-disabled="true"]')) return false;
  if (el.closest('[disabled], [aria-disabled="true"]')) return false;
  if (scopeRoot && !scopeRoot.contains(el)) return false;
  return Boolean(el.closest(INTERACTIVE_SELECTOR));
}

function findInteractiveTarget(el, scopeRoot) {
  if (!el || !(el instanceof Element)) return null;
  if (el.closest('[data-spatial-cursor]')) return null;
  const candidate = el.closest(INTERACTIVE_SELECTOR);
  if (!candidate) return null;
  if (candidate.matches('[disabled], [aria-disabled="true"]')) return null;
  if (scopeRoot && !scopeRoot.contains(candidate)) return null;
  return candidate;
}

function buildWsUrl(apiBase) {
  if (!apiBase) {
    return `ws://${window.location.hostname}:8001/ws/gesture`;
  }
  return `${apiBase.replace(/^http/, 'ws')}/ws/gesture`;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

export default function SpatialCursor({ api, scope }) {
  const [cursor, setCursor] = useState({
    x: 0.5,
    y: 0.5,
    pinch: false,
    active: false,
    pinchDistance: 1,
  });
  const [highlight, setHighlight] = useState(null);
  const [viewport, setViewport] = useState({
    w: window.innerWidth,
    h: window.innerHeight,
  });
  const wsRef = useRef(null);
  const retryRef = useRef(null);
  const pinchRef = useRef(false);
  const targetRef = useRef(null);
  const rafRef = useRef(null);
  const dwellRef = useRef(null);
  const scopeRef = useRef(null);
  const debugEnabled = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('spatialDebug') === '1';
  }, []);

  useEffect(() => {
    const handleResize = () => {
      setViewport({ w: window.innerWidth, h: window.innerHeight });
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    let isMounted = true;

    const connect = () => {
      const wsUrl = buildWsUrl(api);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const pinch = PINCH_GESTURES.has(payload.gesture);
          const active = Boolean(payload.active) && (payload.hand_count || 0) > 0;
          setCursor({
            x: typeof payload.pointer_x === 'number' ? payload.pointer_x : 0.5,
            y: typeof payload.pointer_y === 'number' ? payload.pointer_y : 0.5,
            pinch,
            active,
            pinchDistance: typeof payload.pinch_distance === 'number' ? payload.pinch_distance : 1,
          });
        } catch {
          // Ignore malformed frames.
        }
      };

      ws.onclose = () => {
        if (!isMounted) return;
        retryRef.current = setTimeout(connect, 1000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      isMounted = false;
      if (retryRef.current) {
        clearTimeout(retryRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [api]);

  useEffect(() => {
    if (!scope) {
      scopeRef.current = null;
      return;
    }
    scopeRef.current = document.querySelector(`[data-spatial-scope="${scope}"]`);
  }, [scope]);

  const pixel = useMemo(() => {
    const px = clamp(cursor.x, 0, 1) * viewport.w;
    const py = clamp(cursor.y, 0, 1) * viewport.h;
    return { x: px, y: py };
  }, [cursor.x, cursor.y, viewport.w, viewport.h]);

  useEffect(() => {
    if (!cursor.active) {
      setHighlight(null);
      return;
    }
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }
    rafRef.current = requestAnimationFrame(() => {
      const target = document.elementFromPoint(pixel.x, pixel.y);
      const interactive = findInteractiveTarget(target, scopeRef.current);
      if (!interactive) {
        setHighlight(null);
        return;
      }
      const rect = interactive.getBoundingClientRect();
      setHighlight({
        x: rect.left,
        y: rect.top,
        w: rect.width,
        h: rect.height,
      });
    });
    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [cursor.active, pixel.x, pixel.y]);

  useEffect(() => {
    if (cursor.pinch && !pinchRef.current && !dwellRef.current) {
      dwellRef.current = setTimeout(() => {
        dwellRef.current = null;
        if (!cursor.pinch || pinchRef.current) return;
        const target = findInteractiveTarget(document.elementFromPoint(pixel.x, pixel.y), scopeRef.current);
        if (!target) return;
        pinchRef.current = true;
        targetRef.current = target;
        if (window.PointerEvent) {
          target.dispatchEvent(new PointerEvent('pointerdown', {
            bubbles: true,
            clientX: pixel.x,
            clientY: pixel.y,
            pointerType: 'touch',
            isPrimary: true,
          }));
        }
        target.dispatchEvent(new MouseEvent('mousedown', {
          bubbles: true,
          clientX: pixel.x,
          clientY: pixel.y,
        }));
      }, PINCH_DWELL_MS);
    }

    if (!cursor.pinch && pinchRef.current) {
      pinchRef.current = false;
      const target = targetRef.current;
      targetRef.current = null;
      if (target) {
        if (window.PointerEvent) {
          target.dispatchEvent(new PointerEvent('pointerup', {
            bubbles: true,
            clientX: pixel.x,
            clientY: pixel.y,
            pointerType: 'touch',
            isPrimary: true,
          }));
        }
        target.dispatchEvent(new MouseEvent('mouseup', {
          bubbles: true,
          clientX: pixel.x,
          clientY: pixel.y,
        }));
        target.dispatchEvent(new MouseEvent('click', {
          bubbles: true,
          clientX: pixel.x,
          clientY: pixel.y,
        }));
      }
    }
    if (!cursor.pinch && dwellRef.current) {
      clearTimeout(dwellRef.current);
      dwellRef.current = null;
    }
  }, [cursor.pinch, pixel.x, pixel.y]);

  useEffect(() => {
    if (!pinchRef.current) return;
    const target = targetRef.current;
    if (!target || !isInteractive(target, scopeRef.current)) return;
    if (window.PointerEvent) {
      target.dispatchEvent(new PointerEvent('pointermove', {
        bubbles: true,
        clientX: pixel.x,
        clientY: pixel.y,
        pointerType: 'touch',
        isPrimary: true,
      }));
    }
    target.dispatchEvent(new MouseEvent('mousemove', {
      bubbles: true,
      clientX: pixel.x,
      clientY: pixel.y,
    }));
  }, [pixel.x, pixel.y]);

  const size = cursor.pinch ? 32 : 26;

  return (
    <>
      {highlight && (
        <motion.div
          data-spatial-cursor
          className="pointer-events-none fixed top-0 left-0 z-[1190]"
          animate={{
            x: highlight.x,
            y: highlight.y,
            width: highlight.w,
            height: highlight.h,
            opacity: cursor.active ? 0.85 : 0,
          }}
          transition={{ type: 'spring', stiffness: 240, damping: 26 }}
        >
          <div className="relative h-full w-full">
            <div className="absolute inset-0 border border-dashed border-cyan-300/70 shadow-[0_0_22px_rgba(34,211,238,0.3)]" />
            <div className="absolute inset-0 border border-cyan-400/20" />
            <div className="absolute -top-1 -left-1 h-3 w-3 border-l border-t border-cyan-300/80" />
            <div className="absolute -top-1 -right-1 h-3 w-3 border-r border-t border-cyan-300/80" />
            <div className="absolute -bottom-1 -left-1 h-3 w-3 border-l border-b border-cyan-300/80" />
            <div className="absolute -bottom-1 -right-1 h-3 w-3 border-r border-b border-cyan-300/80" />
          </div>
        </motion.div>
      )}
      <motion.div
        data-spatial-cursor
        className="pointer-events-none fixed top-0 left-0 z-[1200]"
        animate={{
          x: pixel.x - size / 2,
          y: pixel.y - size / 2,
          opacity: cursor.active ? 1 : 0,
          scale: cursor.pinch ? 0.9 : 1,
        }}
        transition={{ type: 'spring', stiffness: 300, damping: 28 }}
      >
        <div
          className="rounded-full border border-cyan-300/80 shadow-[0_0_16px_rgba(34,211,238,0.6)]"
          style={{ width: size, height: size }}
        >
          <div className="h-full w-full rounded-full border border-cyan-400/20" />
        </div>
      </motion.div>
      {debugEnabled && (
        <div
          data-spatial-cursor
          className="pointer-events-none fixed bottom-4 right-4 z-[1210] border border-cyan-500/40 bg-slate-950/80 px-3 py-2 text-[10px] font-mono text-cyan-200"
        >
          <div>SPATIAL DEBUG</div>
          <div>X: {cursor.x.toFixed(3)} Y: {cursor.y.toFixed(3)}</div>
          <div>PINCH: {cursor.pinch ? 'HOLD' : 'OPEN'} DIST: {cursor.pinchDistance.toFixed(3)}</div>
        </div>
      )}
    </>
  );
}
