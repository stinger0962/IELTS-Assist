import { useState, useEffect, useCallback } from 'react';
import { topicsAPI } from '../api';
import { lookupWord } from '../utils/dictionary';
import { useAppStore } from '../store';

interface UseVocabSelectionOptions {
  enabled: boolean;
  skill?: string;
}

export function useVocabSelection({ enabled, skill = 'reading' }: UseVocabSelectionOptions) {
  const language = useAppStore((s: any) => s.language) || 'en';
  const [word, setWord] = useState('');
  const [popupPos, setPopupPos] = useState<{ x: number; y: number } | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [def, setDef] = useState('');
  const [defZh, setDefZh] = useState('');
  const [phonetic, setPhonetic] = useState('');
  const [audioUrl, setAudioUrl] = useState('');
  const [defLoading, setDefLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [duplicate, setDuplicate] = useState(false);
  const [saved, setSaved] = useState(false);

  const openModal = useCallback(async (selectedWord: string) => {
    setWord(selectedWord);
    setDef(''); setDefZh(''); setPhonetic(''); setAudioUrl('');
    setDefLoading(true); setShowModal(true); setPopupPos(null);
    try {
      // One call returns definition, Chinese, IPA and self-hosted audio.
      const entry = await lookupWord(selectedWord);
      setDef(entry.definition_en);
      setPhonetic(entry.phonetic || '');
      setAudioUrl(entry.audio_url || '');
      if (language === 'zh') setDefZh(entry.definition_zh || '');
    } catch {} finally { setDefLoading(false); }
  }, [language]);

  const save = useCallback(async () => {
    if (!def.trim()) return;
    setSaving(true); setDuplicate(false);
    try {
      await topicsAPI.create({
        title: word, content: def, content_zh: defZh || undefined,
        skill, category: 'vocabulary',
        phonetic: phonetic || undefined, audio_url: audioUrl || undefined,
      });
      setSaved(true); setShowModal(false); setDef('');
      setTimeout(() => setSaved(false), 3000);
    } catch (err: any) {
      if (err?.response?.status === 409) setDuplicate(true);
    } finally { setSaving(false); }
  }, [word, def, defZh, skill, phonetic, audioUrl]);

  const closeModal = useCallback(() => {
    setShowModal(false); setDef(''); setDuplicate(false);
  }, []);

  // Text selection listener
  useEffect(() => {
    if (!enabled) { setPopupPos(null); return; }
    let timer: ReturnType<typeof setTimeout>;
    const onSelChange = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const sel = window.getSelection();
        const text = sel?.toString().trim() ?? '';
        if (text.length >= 2 && text.length <= 60 && !text.includes('\n')) {
          try {
            const rect = sel!.getRangeAt(0).getBoundingClientRect();
            setWord(text);
            setPopupPos({ x: rect.left + rect.width / 2, y: rect.bottom });
          } catch {}
        } else { setPopupPos(null); }
      }, 200);
    };
    document.addEventListener('selectionchange', onSelChange);
    return () => { clearTimeout(timer); document.removeEventListener('selectionchange', onSelChange); };
  }, [enabled]);

  return {
    word, setWord, popupPos, showModal, def, setDef, defZh, defLoading,
    phonetic, audioUrl, saving, duplicate, saved,
    openModal, save, closeModal,
  };
}
