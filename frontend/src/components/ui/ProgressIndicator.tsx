import React from "react";
import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

interface StepItem {
  id: number;
  label: string;
}

interface HorizontalStepperProps {
  steps: StepItem[];
  currentStep: number;
  onStepClick?: (stepId: number) => void;
  className?: string;
}

export function HorizontalStepper({
  steps,
  currentStep,
  onStepClick,
  className,
}: HorizontalStepperProps) {
  return (
    <div className={cn("flex items-center justify-between w-full max-w-3xl mx-auto py-2", className)}>
      {steps.map((step, idx) => {
        const isCompleted = step.id < currentStep;
        const isActive = step.id === currentStep;

        return (
          <React.Fragment key={step.id}>
            <div
              onClick={() => onStepClick && onStepClick(step.id)}
              className={cn(
                "flex items-center gap-2 select-none",
                onStepClick ? "cursor-pointer" : "cursor-default"
              )}
            >
              <div
                className={cn(
                  "w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-all duration-200",
                  isActive
                    ? "bg-blue-600 text-white shadow-xs ring-4 ring-blue-50"
                    : isCompleted
                    ? "bg-blue-600 text-white"
                    : "bg-slate-100 text-slate-500 border border-slate-200"
                )}
              >
                {isCompleted ? <Check size={13} className="stroke-[3]" /> : step.id}
              </div>
              <span
                className={cn(
                  "text-xs font-medium transition-colors",
                  isActive
                    ? "text-blue-600 font-semibold"
                    : isCompleted
                    ? "text-slate-800"
                    : "text-slate-500"
                )}
              >
                {step.label}
              </span>
            </div>

            {idx < steps.length - 1 && (
              <div
                className={cn(
                  "flex-1 h-0.5 mx-3 transition-colors",
                  step.id < currentStep ? "bg-blue-600" : "bg-slate-200"
                )}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

interface CircularProgressProps {
  current: number;
  total: number;
  size?: number;
  strokeWidth?: number;
  className?: string;
}

export function CircularProgress({
  current,
  total,
  size = 72,
  strokeWidth = 7,
  className,
}: CircularProgressProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.min(1, Math.max(0, current / total));
  const strokeDashoffset = circumference - progress * circumference;

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="#E2E8F0"
          strokeWidth={strokeWidth}
          fill="transparent"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="#2563EB"
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          className="transition-all duration-500 ease-out"
        />
      </svg>
      <div className="absolute text-center">
        <span className="text-sm font-bold text-slate-800">
          {current}/{total}
        </span>
      </div>
    </div>
  );
}
