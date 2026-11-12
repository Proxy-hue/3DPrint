import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div style={{ padding: '20px', textAlign: 'center' }}>
      <h1>404 - Страница не найдена</h1>
      <Link to="/client">Вернуться на главную</Link>
    </div>
  );
}
