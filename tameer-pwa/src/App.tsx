import { Routes, Route, Navigate } from 'react-router-dom';
import TabBar from './components/shared/TabBar';
import LanguageToggle from './components/shared/LanguageToggle';
import FarmerView from './pages/FarmerView';
import EngineerView from './pages/EngineerView';
import PlantHealthView from './pages/PlantHealthView';

export default function App() {
  return (
    <div className="min-h-screen bg-bg">
      <header className="bg-primary text-white px-4 py-3 flex items-center justify-between sticky top-0 z-10 shadow">
        <TabBar />
        <LanguageToggle />
      </header>
      <main className="max-w-2xl mx-auto px-4 py-4 space-y-4">
        <Routes>
          <Route path="/" element={<FarmerView />} />
          <Route path="/engineer" element={<EngineerView />} />
          <Route path="/plant-health" element={<PlantHealthView />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
