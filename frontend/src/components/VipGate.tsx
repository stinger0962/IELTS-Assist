import { Lock, Sparkles } from 'lucide-react';

interface VipGateProps {
  skillName: string;
}

export default function VipGate({ skillName }: VipGateProps) {
  return (
    <>
      <div className="vip-gate">
        <div className="vip-icon"><Lock size={32} /></div>
        <h3>Full {skillName} Test</h3>
        <p>Full-length IELTS exam simulations are a VIP feature.</p>
        <div className="vip-badge"><Sparkles size={14} /> VIP</div>
      </div>
      <style>{`
        .vip-gate { text-align: center; padding: var(--spacing-2xl) var(--spacing-md); }
        .vip-icon { margin-bottom: var(--spacing-md); color: var(--color-text-secondary); opacity: 0.5; }
        .vip-gate h3 { font-size: 1.1rem; color: var(--color-text-primary); margin-bottom: var(--spacing-xs); }
        .vip-gate p { font-size: 0.85rem; color: var(--color-text-secondary); margin-bottom: var(--spacing-md); line-height: 1.5; }
        .vip-badge { display: inline-flex; align-items: center; gap: 4px; background: linear-gradient(135deg, #F59E0B, #D97706); color: #fff; padding: 6px 16px; border-radius: 20px; font-size: 0.8rem; font-weight: 700; }
      `}</style>
    </>
  );
}
