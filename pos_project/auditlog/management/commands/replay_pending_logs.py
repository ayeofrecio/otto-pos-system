"""
Import log rows that were queued in logs/pending_db_logs.jsonl while the
database was unreachable. Safe to run repeatedly (e.g. every few minutes).
"""
import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from auditlog import conf
from auditlog.models import AuditLog, ErrorLog

MODELS = {'audit': AuditLog, 'error': ErrorLog}


class Command(BaseCommand):
    help = 'Replay log rows queued in the fallback file into the database.'

    def handle(self, *args, **opts):
        path = Path(settings.LOGS_DIR) / conf.get('fallback_file')
        if not path.exists():
            self.stdout.write('Nothing to replay.')
            return
        work = path.with_suffix('.replaying')
        path.replace(work)          # new failures go to a fresh file meanwhile
        failed, done = [], 0
        for line in work.read_text(encoding='utf-8').splitlines():
            try:
                item = json.loads(line)
                fields = item['fields']
                for key in ('created_at', 'last_seen'):
                    if fields.get(key):
                        fields[key] = datetime.fromisoformat(fields[key])
                MODELS[item['model']].objects.create(**fields)
                done += 1
            except Exception:
                failed.append(line)
        if failed:    # keep unprocessed lines for the next run
            with open(path, 'a', encoding='utf-8') as fh:
                fh.write('\n'.join(failed) + '\n')
        work.unlink()
        self.stdout.write(f'Replayed {done} rows, {len(failed)} left for next run.')
