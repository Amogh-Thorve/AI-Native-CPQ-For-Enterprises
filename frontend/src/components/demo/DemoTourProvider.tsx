"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { CheckCircle2, Pause, Play, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  DEMO_STEPS,
  DEFAULT_DEMO_FLAGS,
  accumulateDemoFlags,
  clearDemoTourState,
  readDemoTourState,
  writeDemoTourState,
  type DemoSimulationFlags,
  type DemoStep,
  type DemoToast,
} from "@/lib/demoTour";
import {
  DEMO_CATEGORIES,
  DEMO_CUSTOMERS,
  DEMO_PRICING_PRODUCTS,
  DEMO_PRICING_RULES,
  DEMO_PRICING_WATERFALL,
  DEMO_PRODUCTS,
  buildDemoApprovals,
  buildDemoQuote,
  type DemoApprovalItem,
  type DemoQuoteListItem,
} from "@/lib/demoMockData";
import type { CategoryRead, ProductRead } from "@/types/catalog";
import type { CustomerRead } from "@/types/customer";

interface DemoTourContextValue {
  isActive: boolean;
  isPaused: boolean;
  stepIndex: number;
  step: DemoStep | null;
  totalSteps: number;
  flags: DemoSimulationFlags;
  toast: DemoToast | null;
  mockCustomers: CustomerRead[];
  mockProducts: ProductRead[];
  mockCategories: CategoryRead[];
  mockQuote: DemoQuoteListItem;
  mockQuotes: DemoQuoteListItem[];
  mockApprovals: DemoApprovalItem[];
  mockPricingProducts: typeof DEMO_PRICING_PRODUCTS;
  mockPricingRules: typeof DEMO_PRICING_RULES;
  mockPricingWaterfall: typeof DEMO_PRICING_WATERFALL;
  start: () => void;
  next: () => void;
  prev: () => void;
  stop: () => void;
  togglePause: () => void;
}

const DemoTourContext = createContext<DemoTourContextValue>({
  isActive: false,
  isPaused: false,
  stepIndex: 0,
  step: null,
  totalSteps: DEMO_STEPS.length,
  flags: DEFAULT_DEMO_FLAGS,
  toast: null,
  mockCustomers: DEMO_CUSTOMERS,
  mockProducts: DEMO_PRODUCTS,
  mockCategories: DEMO_CATEGORIES,
  mockQuote: buildDemoQuote("DRAFT"),
  mockQuotes: [buildDemoQuote("DRAFT")],
  mockApprovals: buildDemoApprovals("PENDING"),
  mockPricingProducts: DEMO_PRICING_PRODUCTS,
  mockPricingRules: DEMO_PRICING_RULES,
  mockPricingWaterfall: DEMO_PRICING_WATERFALL,
  start: () => {},
  next: () => {},
  prev: () => {},
  stop: () => {},
  togglePause: () => {},
});

export function useDemoTour() {
  return useContext(DemoTourContext);
}

export const useDemoSimulation = useDemoTour;

function isOnStepRoute(pathname: string, route: string) {
  return pathname === route || pathname.startsWith(`${route}/`);
}

export function DemoTourProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [isActive, setIsActive] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [hydrated, setHydrated] = useState(false);

  const persist = useCallback((active: boolean, index: number) => {
    if (active) {
      writeDemoTourState({ isActive: true, stepIndex: index });
    } else {
      clearDemoTourState();
    }
  }, []);

  const stop = useCallback(() => {
    setIsActive(false);
    setIsPaused(false);
    setStepIndex(0);
    persist(false, 0);
  }, [persist]);

  const start = useCallback(() => {
    setIsActive(true);
    setIsPaused(false);
    setStepIndex(0);
    persist(true, 0);
    const first = DEMO_STEPS[0];
    if (first && typeof window !== "undefined" && !isOnStepRoute(window.location.pathname, first.route)) {
      router.push(first.route);
    }
  }, [persist, router]);

  const next = useCallback(() => {
    setStepIndex((current) => {
      if (current >= DEMO_STEPS.length - 1) {
        setIsActive(false);
        setIsPaused(false);
        persist(false, 0);
        return 0;
      }
      const nextIndex = current + 1;
      persist(true, nextIndex);
      const nextStep = DEMO_STEPS[nextIndex];
      const currentPath = typeof window !== "undefined" ? window.location.pathname : "";
      if (nextStep && !isOnStepRoute(currentPath, nextStep.route)) {
        router.push(nextStep.route);
      }
      return nextIndex;
    });
  }, [persist, router]);

  const prev = useCallback(() => {
    setStepIndex((current) => {
      const prevIndex = Math.max(0, current - 1);
      persist(true, prevIndex);
      const prevStep = DEMO_STEPS[prevIndex];
      const currentPath = typeof window !== "undefined" ? window.location.pathname : "";
      if (prevStep && !isOnStepRoute(currentPath, prevStep.route)) {
        router.push(prevStep.route);
      }
      return prevIndex;
    });
  }, [persist, router]);

  const togglePause = useCallback(() => {
    setIsPaused((value) => !value);
  }, []);

  useEffect(() => {
    const stored = readDemoTourState();
    const timer = window.setTimeout(() => {
      if (stored?.isActive) {
        const safeIndex = Math.min(Math.max(stored.stepIndex, 0), DEMO_STEPS.length - 1);
        setIsActive(true);
        setStepIndex(safeIndex);
      }
      setHydrated(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!hydrated || typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("demo") !== "1") return;
    params.delete("demo");
    const qs = params.toString();
    window.history.replaceState(
      {},
      "",
      `${window.location.pathname}${qs ? `?${qs}` : ""}${window.location.hash}`
    );
    const timer = window.setTimeout(() => start(), 0);
    return () => window.clearTimeout(timer);
  }, [hydrated, pathname, start]);

  useEffect(() => {
    if (!hydrated || !isActive) return;
    const step = DEMO_STEPS[stepIndex];
    if (!step) return;
    if (!isOnStepRoute(pathname, step.route)) {
      router.push(step.route);
    }
  }, [hydrated, isActive, stepIndex, pathname, router]);

  useEffect(() => {
    if (!isActive) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        stop();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isActive, stop]);

  useEffect(() => {
    if (!isActive || isPaused || !hydrated) return;
    if (stepIndex >= DEMO_STEPS.length - 1) return;
    const step = DEMO_STEPS[stepIndex];
    const ms = step?.durationMs ?? 5500;
    const timer = window.setTimeout(() => next(), ms);
    return () => window.clearTimeout(timer);
  }, [isActive, isPaused, hydrated, stepIndex, next]);

  const step = isActive ? DEMO_STEPS[stepIndex] ?? null : null;
  const flags = useMemo(
    () => (isActive ? accumulateDemoFlags(stepIndex) : DEFAULT_DEMO_FLAGS),
    [isActive, stepIndex]
  );

  const mockQuote = useMemo(
    () => buildDemoQuote(flags.quoteSubmitted || flags.approvalDecided ? "SUBMITTED" : "DRAFT"),
    [flags.quoteSubmitted, flags.approvalDecided]
  );

  const mockApprovals = useMemo(
    () => buildDemoApprovals(flags.approvalDecided ? "APPROVED" : "PENDING"),
    [flags.approvalDecided]
  );

  const value = useMemo(
    () => ({
      isActive,
      isPaused,
      stepIndex,
      step,
      totalSteps: DEMO_STEPS.length,
      flags,
      toast: step?.toast ?? null,
      mockCustomers: DEMO_CUSTOMERS,
      mockProducts: DEMO_PRODUCTS,
      mockCategories: DEMO_CATEGORIES,
      mockQuote,
      mockQuotes: [mockQuote],
      mockApprovals,
      mockPricingProducts: DEMO_PRICING_PRODUCTS,
      mockPricingRules: DEMO_PRICING_RULES,
      mockPricingWaterfall: DEMO_PRICING_WATERFALL,
      start,
      next,
      prev,
      stop,
      togglePause,
    }),
    [isActive, isPaused, stepIndex, step, flags, mockQuote, mockApprovals, start, next, prev, stop, togglePause]
  );

  return (
    <DemoTourContext.Provider value={value}>
      {children}
      {isActive && step && <DemoTourOverlay step={step} stepIndex={stepIndex} />}
      {isActive && step?.toast && <DemoSimulationToast toast={step.toast} />}
    </DemoTourContext.Provider>
  );
}

function DemoSimulationToast({ toast }: { toast: DemoToast }) {
  return (
    <div className="fixed top-16 right-6 z-[70] pointer-events-none max-w-sm">
      <div
        className={`pointer-events-auto rounded-xl border shadow-lg p-3.5 flex items-start gap-3 bg-white ${
          toast.variant === "success" ? "border-emerald-200" : "border-teal-200"
        }`}
        role="status"
      >
        <CheckCircle2
          size={18}
          className={toast.variant === "success" ? "text-emerald-600 shrink-0 mt-0.5" : "text-teal-600 shrink-0 mt-0.5"}
        />
        <div>
          <p className="text-xs font-bold text-slate-900">{toast.title}</p>
          <p className="text-[11px] text-slate-600 mt-0.5 leading-relaxed">{toast.body}</p>
        </div>
      </div>
    </div>
  );
}

function DemoTourOverlay({ step, stepIndex }: { step: DemoStep; stepIndex: number }) {
  const { next, prev, stop, totalSteps, isPaused, togglePause } = useDemoTour();
  const pathname = usePathname();
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [viewport, setViewport] = useState({ width: 1024, height: 768 });

  useEffect(() => {
    const syncViewport = () => setViewport({ width: window.innerWidth, height: window.innerHeight });
    syncViewport();
    window.addEventListener("resize", syncViewport);
    return () => window.removeEventListener("resize", syncViewport);
  }, []);

  useEffect(() => {
    if (!isOnStepRoute(pathname, step.route)) {
      return;
    }

    let cancelled = false;
    let frame = 0;
    let didScroll = false;
    const selector = step.target;

    const measure = () => {
      const target =
        (selector ? document.querySelector(selector) : null) ?? document.querySelector("main");
      if (!target) {
        setRect(null);
        return;
      }
      setRect(target.getBoundingClientRect());
      if (!didScroll) {
        didScroll = true;
        target.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
      }
    };

    const timer = window.setTimeout(() => {
      if (cancelled) return;
      let attempts = 0;
      const tryMeasure = () => {
        if (cancelled) return;
        const target =
          (selector ? document.querySelector(selector) : null) ??
          (attempts >= 4 ? document.querySelector("main") : null);
        if (target) {
          setRect(target.getBoundingClientRect());
          if (!didScroll) {
            didScroll = true;
            target.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
          }
          return;
        }
        attempts += 1;
        if (attempts < 8) {
          window.setTimeout(tryMeasure, 150);
        }
      };
      tryMeasure();
    }, 300);

    const onRelayout = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(measure);
    };

    window.addEventListener("resize", onRelayout);
    window.addEventListener("scroll", onRelayout, true);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", onRelayout);
      window.removeEventListener("scroll", onRelayout, true);
    };
  }, [step, pathname, stepIndex]);

  const pad = 8;
  const activeRect = isOnStepRoute(pathname, step.route) ? rect : null;
  const spotlight = activeRect
    ? {
        top: Math.max(activeRect.top - pad, 8),
        left: Math.max(activeRect.left - pad, 8),
        width: Math.min(activeRect.width + pad * 2, viewport.width - 16),
        height: Math.min(activeRect.height + pad * 2, viewport.height - 16),
      }
    : {
        top: Math.max(viewport.height / 2 - 40, 80),
        left: Math.max(viewport.width / 2 - 160, 12),
        width: 320,
        height: 80,
      };

  const tooltipWidth = 360;
  const tooltipMaxH = 280;
  const spaceBelow = viewport.height - (spotlight.top + spotlight.height);
  const placeBelow = spaceBelow > tooltipMaxH + 16 || spotlight.top < tooltipMaxH + 24;
  const tooltipLeft = Math.min(
    Math.max(spotlight.left, 12),
    viewport.width - tooltipWidth - 12
  );

  const tooltipStyle: React.CSSProperties = placeBelow
    ? { top: spotlight.top + spotlight.height + 12, left: tooltipLeft }
    : { bottom: viewport.height - spotlight.top + 12, left: tooltipLeft };

  const isLast = stepIndex >= totalSteps - 1;

  return (
    <div className="fixed inset-0 z-[60] pointer-events-none" aria-live="polite">
      <div
        className="absolute rounded-xl transition-all duration-200"
        style={{
          top: spotlight.top,
          left: spotlight.left,
          width: spotlight.width,
          height: spotlight.height,
          boxShadow: "0 0 0 9999px rgba(15, 23, 42, 0.62)",
          outline: "2px solid rgb(13 148 136)",
        }}
      />
      <div
        role="dialog"
        aria-labelledby="demo-tour-title"
        className="absolute pointer-events-auto w-[min(360px,calc(100vw-24px))] rounded-xl border border-teal-200/80 bg-white shadow-xl p-4 space-y-3"
        style={tooltipStyle}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-teal-700 flex items-center gap-1">
              <Sparkles size={11} />
              Guided demo
            </p>
            <h2 id="demo-tour-title" className="text-sm font-bold text-slate-900 mt-0.5">
              {step.title}
            </h2>
          </div>
          <span className="text-[11px] font-semibold text-slate-500 tabular-nums shrink-0">
            {stepIndex + 1}/{totalSteps}
          </span>
        </div>
        <p className="text-xs text-slate-600 leading-relaxed">{step.body}</p>
        <div className="flex items-center justify-between gap-2 pt-1">
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" onClick={stop}>
              Skip
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={togglePause}
              icon={isPaused ? <Play size={12} /> : <Pause size={12} />}
            >
              {isPaused ? "Play" : "Pause"}
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={prev} disabled={stepIndex === 0}>
              Back
            </Button>
            <Button variant="primary" size="sm" onClick={next}>
              {isLast ? "Done" : "Next"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
