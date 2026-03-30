import { useEffect, useState, useRef } from 'react';
import { playAchievement } from '../hooks/useSoundEffects';

// ─── Confetti Burst ─────────────────────────────────────────────────────────
// Drop this component anywhere to trigger a one-time confetti burst on mount.

const CONFETTI_COLORS = ['#4F46E5', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4'];
const PARTICLE_COUNT = 40;

export function ConfettiBurst() {
  useEffect(() => { playAchievement(); }, []);
  const [particles] = useState(() =>
    Array.from({ length: PARTICLE_COUNT }, (_, i) => ({
      id: i,
      color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
      x: (Math.random() - 0.5) * 300,
      y: -(Math.random() * 200 + 100),
      rotate: Math.random() * 720 - 360,
      scale: Math.random() * 0.6 + 0.4,
      delay: Math.random() * 300,
      shape: Math.random() > 0.5 ? 'square' : 'circle',
    }))
  );

  return (
    <>
      <div className="confetti-container" aria-hidden="true">
        {particles.map((p) => (
          <div
            key={p.id}
            className={`confetti-particle confetti-${p.shape}`}
            style={{
              '--x': `${p.x}px`,
              '--y': `${p.y}px`,
              '--r': `${p.rotate}deg`,
              '--s': p.scale,
              '--delay': `${p.delay}ms`,
              backgroundColor: p.color,
            } as React.CSSProperties}
          />
        ))}
      </div>
      <style>{confettiStyles}</style>
    </>
  );
}

const confettiStyles = `
  .confetti-container {
    position: fixed;
    top: 40%;
    left: 50%;
    width: 0;
    height: 0;
    pointer-events: none;
    z-index: 9999;
  }
  .confetti-particle {
    position: absolute;
    width: 8px;
    height: 8px;
    animation: confetti-fly 1.8s ease-out forwards;
    animation-delay: var(--delay);
    opacity: 0;
  }
  .confetti-square { border-radius: 1px; }
  .confetti-circle { border-radius: 50%; }

  @keyframes confetti-fly {
    0% { opacity: 1; transform: translate(0, 0) rotate(0deg) scale(1); }
    20% { opacity: 1; }
    100% {
      opacity: 0;
      transform: translate(var(--x), var(--y)) rotate(var(--r)) scale(var(--s));
    }
  }
`;


// ─── Personal Best Badge ────────────────────────────────────────────────────
// Shows a gold "Personal Best!" badge with sparkle animation.

export function PersonalBestBadge() {
  return (
    <>
      <div className="pb-badge">
        <span className="pb-sparkle">✨</span>
        <span className="pb-text">Personal Best!</span>
        <span className="pb-sparkle">✨</span>
      </div>
      <style>{pbStyles}</style>
    </>
  );
}

const pbStyles = `
  .pb-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: linear-gradient(135deg, #F59E0B, #D97706);
    color: #fff;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 700;
    animation: pb-pop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) both;
    animation-delay: 0.5s;
    box-shadow: 0 2px 10px rgba(245, 158, 11, 0.4);
  }
  @keyframes pb-pop {
    0% { opacity: 0; transform: scale(0.3); }
    100% { opacity: 1; transform: scale(1); }
  }
  .pb-sparkle {
    font-size: 0.7rem;
    animation: pb-twinkle 1.5s ease-in-out infinite;
  }
  .pb-sparkle:last-child { animation-delay: 0.5s; }
  @keyframes pb-twinkle {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(0.8); }
  }
`;


// ─── Score Count-Up ─────────────────────────────────────────────────────────
// Animates a number from 0 to the target value over ~1 second.

export function CountUp({ value, decimals = 1, suffix = '', prefix = '', duration = 1000, className = '' }: {
  value: number;
  decimals?: number;
  suffix?: string;
  prefix?: string;
  duration?: number;
  className?: string;
}) {
  const [display, setDisplay] = useState(0);
  const frameRef = useRef<number>(0);
  const startRef = useRef<number>(0);

  useEffect(() => {
    startRef.current = performance.now();
    const animate = (now: number) => {
      const elapsed = now - startRef.current;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(eased * value);
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      }
    };
    frameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameRef.current);
  }, [value, duration]);

  return (
    <span className={className}>
      {prefix}{display.toFixed(decimals)}{suffix}
    </span>
  );
}


// ─── Streak Fire ────────────────────────────────────────────────────────────
// Animated fire icon for active streaks.

export function StreakFire({ days }: { days: number }) {
  if (days <= 0) return <span style={{ fontSize: '1.5rem', opacity: 0.3 }}>🔥</span>;
  return (
    <>
      <span className="streak-fire">🔥</span>
      <style>{fireStyles}</style>
    </>
  );
}

const fireStyles = `
  .streak-fire {
    font-size: 1.5rem;
    display: inline-block;
    animation: fire-flicker 1.5s ease-in-out infinite;
    filter: drop-shadow(0 0 4px rgba(245, 158, 11, 0.5));
  }
  @keyframes fire-flicker {
    0%, 100% { transform: scale(1) rotate(0deg); }
    25% { transform: scale(1.05) rotate(-2deg); }
    50% { transform: scale(0.95) rotate(1deg); }
    75% { transform: scale(1.08) rotate(-1deg); }
  }
`;
