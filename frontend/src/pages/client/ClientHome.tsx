import { Link } from 'react-router-dom';

export default function ClientHome() {
  return (
    <div style={{ padding: '20px' }}>
      <h1>Клиентский портал</h1>
      <p>Здесь клиент будет загружать 3D-модели и оформлять заказы.</p>
      <Link to="/manager">Перейти в АРМ Менеджера (для теста)</Link>
    </div>
  );
}
