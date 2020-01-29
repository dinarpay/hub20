# Generated by Django 2.2.9 on 2020-01-29 11:13

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import hub20.apps.blockchain.fields
import hub20.apps.ethereum_money.models
import model_utils.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('blockchain', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EthereumAccount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('address', hub20.apps.blockchain.fields.EthereumAddressField(db_index=True, unique=True)),
                ('private_key', hub20.apps.blockchain.fields.HexField(max_length=64, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='EthereumToken',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chain', models.PositiveIntegerField(choices=[(1, 'Mainnet'), (2, 'Test Network'), (3, 'Ropsten'), (4, 'Rinkeby'), (5, 'Görli'), (42, 'Kovan')])),
                ('ticker', models.CharField(max_length=8)),
                ('name', models.CharField(max_length=500)),
                ('decimals', models.PositiveIntegerField(default=18)),
                ('address', hub20.apps.blockchain.fields.EthereumAddressField(blank=True, null=True)),
            ],
            options={
                'unique_together': {('chain', 'address'), ('chain', 'ticker')},
            },
        ),
        migrations.CreateModel(
            name='ExchangeRate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('currency_code', models.CharField(db_index=True, max_length=3)),
                ('rate', models.DecimalField(decimal_places=18, max_digits=30)),
                ('token', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ethereum_money.EthereumToken')),
            ],
            options={
                'ordering': ('created',),
            },
        ),
        migrations.CreateModel(
            name='CoingeckoDefinition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=256)),
                ('description', models.TextField(null=True)),
                ('logo_url', models.URLField(max_length=500, null=True)),
                ('coingecko_rank', models.PositiveIntegerField(db_index=True, null=True)),
                ('coingecko_score', models.FloatField(null=True)),
                ('developer_score', models.FloatField(null=True)),
                ('liquidity_score', models.FloatField(null=True)),
                ('token', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='coingecko', to='ethereum_money.EthereumToken')),
            ],
        ),
        migrations.CreateModel(
            name='AccountBalanceEntry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', hub20.apps.ethereum_money.models.EthereumTokenAmountField(decimal_places=18, max_digits=32)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='balance_entries', to='ethereum_money.EthereumAccount')),
                ('currency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ethereum_money.EthereumToken')),
                ('transaction', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='blockchain.Transaction')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
