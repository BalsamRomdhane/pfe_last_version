from django.core.management.base import BaseCommand
from django.core.management import call_command
import os

class Command(BaseCommand):
    help = 'Convert root dump.json to UTF-8 and load it via loaddata'

    def handle(self, *args, **options):
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        src = os.path.join(base, 'dump.json')
        if not os.path.exists(src):
            self.stderr.write('dump.json not found at project root')
            return
        dst_dir = os.path.join(base, 'backend', 'fixtures')
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, 'dump_utf8.json')

        # Try common encodings
        encodings = ['utf-8', 'utf-16', 'utf-16-le', 'utf-16-be']
        text = None
        with open(src, 'rb') as f:
            b = f.read()
        for e in encodings:
            try:
                text = b.decode(e)
                self.stdout.write(f'Decoded dump.json with {e}')
                break
            except Exception:
                text = None
        if text is None:
            self.stderr.write('Failed to decode dump.json with common encodings')
            return

        with open(dst, 'w', encoding='utf-8') as f:
            f.write(text)
        self.stdout.write(f'Wrote UTF-8 fixture to {dst}')

        try:
            call_command('loaddata', dst)
            self.stdout.write('loaddata completed')
        except Exception as e:
            self.stderr.write('loaddata failed: ' + str(e))
