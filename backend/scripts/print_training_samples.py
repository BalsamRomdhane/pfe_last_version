#!/usr/bin/env python3
"""Print a summary of current TrainingSample entries for debugging."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from api.models import TrainingSample


def main():
    count = TrainingSample.objects.count()
    print(f'TrainingSample count: {count}')

    sample = TrainingSample.objects.first()
    if sample is None:
        print('No training samples found.')
        return

    print('First sample label:', sample.label)
    print('First sample features:')
    print(sample.features)


if __name__ == '__main__':
    main()
