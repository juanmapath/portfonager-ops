# Generated for dynamic leverage and macro regimes

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('botops', '0023_botasset_cap_lever_botasset_leverage_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='botasset',
            name='max_leverage',
            field=models.FloatField(default=1.0),
        ),
        migrations.AddField(
            model_name='botasset',
            name='current_leverage',
            field=models.FloatField(default=1.0),
        ),
        migrations.AddField(
            model_name='botasset',
            name='use_regimes',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='TradeHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('regime', models.CharField(default='default', max_length=50)),
                ('signal_type', models.CharField(blank=True, max_length=100, null=True)),
                ('pnl', models.FloatField(default=0.0)),
                ('position_side', models.IntegerField(default=1)),
                ('entry_price', models.FloatField(default=0.0)),
                ('exit_price', models.FloatField(default=0.0)),
                ('qty', models.FloatField(default=0.0)),
                ('leverage_applied', models.FloatField(default=1.0)),
                ('entry_date', models.DateField(blank=True, null=True)),
                ('exit_date', models.DateField(default=django.utils.timezone.now)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('assetbot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trade_histories', to='botops.botasset')),
            ],
        ),
    ]
