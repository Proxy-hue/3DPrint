import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ClientHome from './pages/client/ClientHome';
import ManagerDashboard from './pages/manager/ManagerDashboard';
import NotFound from './pages/NotFound';
import './App.css'; // Если он есть, или удалите эту строку

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* При заходе на корень сайта - редирект на клиента */}
        <Route path="/" element={<Navigate to="/client" replace />} />
        
        {/* Маршруты Клиента */}
        <Route path="/client" element={<ClientHome />} />
        
        {/* Маршруты Менеджера */}
        <Route path="/manager" element={<ManagerDashboard />} />
        
        {/* Обработка 404 */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
