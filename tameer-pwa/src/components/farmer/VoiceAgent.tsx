import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import client from '../../api/client';

type AgentState = 'idle' | 'recording' | 'processing' | 'speaking' | 'error';

interface Props {
  zoneId: number;
}

export default function VoiceAgent({ zoneId }: Props) {
  const { t, i18n } = useTranslation();
  const [agentState, setAgentState] = useState<AgentState>('idle');
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [showCard, setShowCard] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const isArabic = i18n.language === 'ar';
  const speechLang = isArabic ? 'ar-EG' : 'en-US';

  const SR = typeof window !== 'undefined'
    ? (window.SpeechRecognition ?? (window as Window & { webkitSpeechRecognition?: typeof SpeechRecognition }).webkitSpeechRecognition)
    : undefined;

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
      window.speechSynthesis?.cancel();
    };
  }, []);

  const statusLabel: Record<AgentState, string> = {
    idle: t('farmer.voice.tapToSpeak'),
    recording: t('farmer.voice.listening'),
    processing: t('farmer.voice.processing'),
    speaking: t('farmer.voice.speaking'),
    error: t('farmer.voice.errorApi'),
  };

  function speak(text: string) {
    setAgentState('speaking');
    const base = (client.defaults.baseURL ?? '').replace(/\/$/, '');
    const url = `${base}/voice/tts?text=${encodeURIComponent(text)}&lang=${isArabic ? 'ar' : 'en'}`;
    const audio = new Audio(url);
    audio.onended = () => setAgentState('idle');
    audio.onerror = () => setAgentState('idle');
    audio.play().catch(() => setAgentState('idle'));
  }

  async function handleMic() {
    if (agentState === 'recording') {
      recognitionRef.current?.stop();
      return;
    }
    if (agentState !== 'idle' && agentState !== 'error') return;
    if (!SR) { setAgentState('error'); return; }

    const rec = new SR();
    rec.lang = speechLang;
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    recognitionRef.current = rec;

    rec.onstart = () => {
      setAgentState('recording');
      setQuestion('');
      setAnswer('');
      setShowCard(true);
    };

    rec.onresult = async (e: SpeechRecognitionEvent) => {
      const transcript = e.results[0][0].transcript;
      setQuestion(transcript);
      setAnswer('');
      setAgentState('processing');

      try {
        const { data } = await client.post<{ answer: string }>('/voice/query', {
          question: transcript,
          zone_id: zoneId,
          language: isArabic ? 'ar' : 'en',
        });
        setAnswer(data.answer);
        speak(data.answer);
      } catch {
        setAgentState('error');
      }
    };

    rec.onerror = (e: SpeechRecognitionErrorEvent) => {
      const msg = e.error === 'not-allowed'
        ? t('farmer.voice.errorMic')
        : e.error === 'language-not-supported'
        ? t('farmer.voice.errorLang')
        : t('farmer.voice.errorApi');
      setQuestion(msg);
      setAnswer('');
      setShowCard(true);
      setAgentState('error');
    };

    // if recognition ended with no result, show a prompt to try again
    rec.onend = () => setAgentState(prev => {
      if (prev === 'recording') {
        setQuestion(t('farmer.voice.noSpeech'));
        return 'error';
      }
      return prev;
    });

    rec.start();
  }

  if (!SR) return null;

  return (
    <>
      {showCard && (
        <div
          className={`fixed bottom-24 right-4 left-4 max-w-sm mx-auto bg-white rounded-2xl shadow-lg p-4 border border-primary/20 z-40 ${isArabic ? 'text-right' : 'text-left'}`}
          dir={isArabic ? 'rtl' : 'ltr'}
        >
          <button
            onClick={() => setShowCard(false)}
            className="absolute top-2 right-2 text-gray-400 hover:text-gray-600 text-xl leading-none px-1"
            aria-label="close"
          >
            ×
          </button>
          {question && (
            <p className="text-xs text-gray-400 mb-1 pr-4 truncate">{question}</p>
          )}
          {answer ? (
            <p className="text-sm text-gray-800 leading-relaxed">{answer}</p>
          ) : (
            <p className="text-sm text-gray-400 animate-pulse">{statusLabel[agentState]}</p>
          )}
        </div>
      )}

      <button
        onClick={handleMic}
        aria-label={statusLabel[agentState]}
        title={statusLabel[agentState]}
        className={`fixed bottom-6 right-4 z-50 w-14 h-14 rounded-full shadow-lg flex items-center justify-center transition-all select-none
          ${agentState === 'recording'
            ? 'bg-red-500 animate-pulse scale-110'
            : agentState === 'speaking'
            ? 'bg-green-500'
            : agentState === 'processing'
            ? 'bg-yellow-400'
            : agentState === 'error'
            ? 'bg-gray-400'
            : 'bg-primary hover:bg-primary/90 active:scale-95'
          }`}
      >
        {agentState === 'processing' ? (
          <svg className="w-6 h-6 text-white animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
        ) : (
          <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2H3v2a9 9 0 0 0 8 8.94V22h-2v2h6v-2h-2v-1.06A9 9 0 0 0 21 12v-2h-2z" />
          </svg>
        )}
      </button>
    </>
  );
}
