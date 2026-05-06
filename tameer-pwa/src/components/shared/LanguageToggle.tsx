import { useTranslation } from 'react-i18next';
import { setLanguage } from '../../i18n';

export default function LanguageToggle() {
  const { t, i18n } = useTranslation();
  const toggle = () => setLanguage(i18n.language === 'en' ? 'ar' : 'en');

  return (
    <button
      onClick={toggle}
      className="border border-white/60 text-white text-xs px-3 py-1 rounded-full hover:bg-white/10 transition-colors"
    >
      {t('common.langToggle')}
    </button>
  );
}
