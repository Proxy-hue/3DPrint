import { Link } from 'react-router-dom'
import { InfoBox } from '../../components/ui'

/** Временная заглушка: АРМ менеджера относится к зоне ответственности А. Д. Колотухина. */
export default function ManagerPlaceholder() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">АРМ менеджера</h1>
      <InfoBox>
        Это временный клиентский фронтенд. Полноценный АРМ менеджера (зона ответственности А. Д. Колотухина)
        подключается из отдельной ветки разработки. Для администрирования справочников используйте{' '}
        <a href="/admin/" className="underline">Django Admin</a> или перейдите на{' '}
        <Link to="/orders" className="underline">клиентский портал</Link>.
      </InfoBox>
    </div>
  )
}
