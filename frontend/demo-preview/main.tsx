import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import FullMockPreviewPractice, { type FullMockPreview } from '../src/components/experimental/FullMockPreviewPractice';
import './style.css';

function Demo() {
  const generation = useRef(0);
  const [skill, setSkill] = useState('reading');
  const [attempt, setAttempt] = useState(1);
  const [preview, setPreview] = useState<FullMockPreview | null>(null);
  const [result, setResult] = useState<{correct: number; total: number} | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    const started = generation.current;
    const current = () => !controller.signal.aborted && started === generation.current;
    fetch('/preview/' + skill, {signal: controller.signal})
      .then(r => { if (!r.ok) throw Error(); return r.json(); })
      .then(nextPreview => { if (current()) setPreview(nextPreview); })
      .catch(() => { if (current()) setError('Preview unavailable'); });
    return () => controller.abort();
  }, [skill, attempt]);
  function resetAttempt() {
    generation.current++;
    setPreview(null);
    setResult(null);
    setError('');
  }
  return <main>
    <header><h1>Synthetic mock laboratory</h1>
      <p>Local-only experiment. Not an IELTS band or a real exam. Listening has no audio asset.</p>
      <label>Skill <select value={skill} onChange={e => { resetAttempt(); setSkill(e.target.value); }}>
        <option value="reading">Reading</option><option value="listening">Listening</option>
      </select></label> <button onClick={() => { resetAttempt(); setAttempt(n => n + 1); }}>New attempt</button>
    </header>
    {error && <p role="alert">{error}</p>}
    {preview && <FullMockPreviewPractice key={skill + attempt} preview={preview} attemptId={skill + attempt}
      onSubmit={async submission => {
        const started = generation.current;
        const response = await fetch('/score/' + skill, {
          method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(submission),
        });
        if (!response.ok) throw Error('Scoring failed');
        const result = await response.json();
        if (started === generation.current) setResult(result);
      }} />}
    {result && <h2 role="status">Raw result: {result.correct} / {result.total}</h2>}
  </main>;
}
createRoot(document.getElementById('root')!).render(<Demo />);
