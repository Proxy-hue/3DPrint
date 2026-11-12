import { Link } from 'react-router-dom';

export default function ManagerDashboard() {
  return (
    <div style={{ padding: '20px' }}>
      <h1>АРМ Менеджера</h1>
      <p>Здесь менеджер будет видеть очередь заказов и распределять их.</p>
      <Link to="/client">Перейти на Портал Клиента</Link>
    </div>
  );
}
