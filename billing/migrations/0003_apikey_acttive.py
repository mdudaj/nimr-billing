# Generated by Django 4.2.9 on 2024-08-03 04:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_apikey'),
    ]

    operations = [
        migrations.AddField(
            model_name='apikey',
            name='acttive',
            field=models.BooleanField(default=True),
        ),
    ]