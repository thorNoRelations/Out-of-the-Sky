
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='Flight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('flightNumber', models.CharField(blank=True, db_index=True, max_length=20, null=True)),
                ('airline', models.CharField(blank=True, max_length=40, null=True)),
                ('depIata', models.CharField(blank=True, db_index=True, max_length=10, null=True)),
                ('arrIata', models.CharField(blank=True, db_index=True, max_length=10, null=True)),
                ('status', models.CharField(blank=True, max_length=20, null=True)),
                ('depTime', models.CharField(blank=True, max_length=40, null=True)),
                ('arrTime', models.CharField(blank=True, max_length=40, null=True)),
                ('lastUpdated', models.DateTimeField(auto_now=True)),
                ('providerSource', models.CharField(db_index=True, max_length=40)),
                ('rawJson', models.JSONField(blank=True, null=True)),
                ('queryHash', models.CharField(db_index=True, max_length=64)),
            ],
            options={'indexes': [models.Index(fields=['flightNumber', 'depIata', 'arrIata', 'providerSource'], name='ix_flights_composite')],},
        ),
        migrations.CreateModel(
            name='AirportWeather',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('icao', models.CharField(blank=True, db_index=True, max_length=10, null=True)),
                ('iata', models.CharField(blank=True, db_index=True, max_length=10, null=True)),
                ('observedAt', models.CharField(blank=True, max_length=40, null=True)),
                ('forecastStart', models.CharField(blank=True, max_length=40, null=True)),
                ('forecastEnd', models.CharField(blank=True, max_length=40, null=True)),
                ('conditionsJson', models.JSONField(blank=True, null=True)),
                ('providerSource', models.CharField(db_index=True, max_length=40)),
                ('lastUpdated', models.DateTimeField(auto_now=True)),
                ('key', models.CharField(db_index=True, max_length=40)),
            ],
        ),
        migrations.CreateModel(
            name='MapsGeo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('queryHash', models.CharField(db_index=True, max_length=64)),
                ('resultJson', models.JSONField(blank=True, null=True)),
                ('providerSource', models.CharField(db_index=True, max_length=40)),
                ('lastUpdated', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
