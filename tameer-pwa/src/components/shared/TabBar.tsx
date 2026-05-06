import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export default function TabBar() {
  const { t } = useTranslation();
  const base = 'px-4 py-1 rounded-full text-sm font-semibold transition-colors';
  const active = 'bg-white text-primary';
  const inactive = 'text-white/80 hover:text-white';

  return (
    <nav className="flex gap-2">
      <NavLink to="/" end className={({ isActive }) => `${base} ${isActive ? active : inactive}`}>
        🌱 {t('tabs.farmer')}
      </NavLink>
      <NavLink to="/engineer" className={({ isActive }) => `${base} ${isActive ? active : inactive}`}>
        📊 {t('tabs.engineer')}
      </NavLink>
    </nav>
  );
}
