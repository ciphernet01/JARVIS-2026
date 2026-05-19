import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Lightbulb, Mic, Hand, CheckCircle2, ChevronRight } from 'lucide-react';

const TUTORIAL_STEPS = [
  {
    id: 'intro',
    title: 'Neural Link Established',
    content: 'Welcome, Sir. I am JARVIS. This tutorial will calibrate your interaction with the neural shell.',
    icon: <Lightbulb className="text-cyan-400" />,
    action: 'Click to begin calibration'
  },
  {
    id: 'voice',
    title: 'Voice Command Calibration',
    content: 'Try saying "What is the system status?". I will process your intent locally via Whisper.',
    icon: <Mic className="text-secondary" />,
    hint: 'Wait for the pulse animation'
  },
  {
    id: 'gesture',
    title: 'Spatial Computing Calibration',
    content: 'Raise your hand. Point your index finger to move the virtual cursor. Pinch to drag elements.',
    icon: <Hand className="text-accent" />,
    hint: 'The HUD will highlight your hand'
  },
  {
    id: 'complete',
    title: 'Calibration Complete',
    content: 'System is fully synchronized. You are now authorized to operate the neural shell.',
    icon: <CheckCircle2 className="text-success" />,
    action: 'Enter Dashboard'
  }
];

export default function NeuralTutorial({ onComplete }) {
  const [currentStep, setCurrentStep] = useState(0);
  const step = TUTORIAL_STEPS[currentStep];

  const next = () => {
    if (currentStep < TUTORIAL_STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      onComplete();
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/40 backdrop-blur-md">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md border border-cyan-500/30 bg-slate-900/90 p-8 shadow-[0_0_50px_rgba(6,182,212,0.2)]"
      >
        <div className="flex items-center gap-4 mb-6">
          <div className="p-3 bg-cyan-950/40 border border-cyan-500/20 rounded-full">
            {step.icon}
          </div>
          <div>
            <h2 className="font-display text-[10px] tracking-[0.2em] uppercase text-cyan-500/60">Step {currentStep + 1} of 4</h2>
            <h1 className="font-display text-lg tracking-tight uppercase text-cyan-100">{step.title}</h1>
          </div>
        </div>

        <p className="font-mono text-sm text-cyan-100/80 mb-8 leading-relaxed">
          {step.content}
        </p>

        {step.hint && (
          <div className="mb-8 p-3 border border-cyan-900/20 bg-cyan-950/10 font-mono text-[10px] text-cyan-400/60 italic">
            Neural Hint: {step.hint}
          </div>
        )}

        <button
          onClick={next}
          className="w-full flex items-center justify-between px-6 py-3 border border-cyan-500/50 text-cyan-300 font-display text-[10px] tracking-[0.25em] uppercase hover:bg-cyan-950/40 hover:text-cyan-100 transition-all"
        >
          {step.action || 'Synchronize & Continue'}
          <ChevronRight size={14} />
        </button>

        {/* Progress Dots */}
        <div className="flex justify-center gap-2 mt-8">
          {TUTORIAL_STEPS.map((_, i) => (
            <div
              key={i}
              className={`w-1.5 h-1.5 rounded-full transition-all duration-500 ${i === currentStep ? 'bg-cyan-400 w-4' : 'bg-cyan-900'}`}
            />
          ))}
        </div>
      </motion.div>
    </div>
  );
}
