import time

from django.core.management.base import BaseCommand

from notifications.services import retry_due_emails


class Command(BaseCommand):
    help = 'Повторная отправка email-уведомлений (5, 15, 60 минут)'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true', help='Непрерывный цикл опроса')
        parser.add_argument('--sleep', type=int, default=60, help='Интервал опроса в секундах (по умолчанию 60)')

    def handle(self, *args, **opts):
        if not opts.get('loop'):
            self.stdout.write(f'Обработано: {retry_due_emails()}')
            return
        sleep_sec = max(1, opts.get('sleep', 60))
        self.stdout.write(f'Запуск цикла retry_notifications каждые {sleep_sec} с...')
        try:
            while True:
                count = retry_due_emails()
                if count > 0:
                    self.stdout.write(f'Обработано: {count}')
                time.sleep(sleep_sec)
        except KeyboardInterrupt:
            self.stdout.write('Остановлено.')
