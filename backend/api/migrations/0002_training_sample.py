from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrainingSample',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('features', models.JSONField()),
                ('label', models.CharField(max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('document', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='training_sample', to='api.document')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
