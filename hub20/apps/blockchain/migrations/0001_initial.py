# Generated by Django 2.2.9 on 2020-01-28 12:02

import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion
import hub20.apps.blockchain.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Block',
            fields=[
                ('hash', hub20.apps.blockchain.fields.HexField(max_length=64, primary_key=True, serialize=False)),
                ('chain', models.PositiveIntegerField(choices=[(1, 'Mainnet'), (2, 'Test Network'), (3, 'Ropsten'), (4, 'Rinkeby'), (5, 'Görli'), (42, 'Kovan')], default=1)),
                ('number', models.PositiveIntegerField(db_index=True)),
                ('timestamp', models.DateTimeField()),
                ('parent_hash', hub20.apps.blockchain.fields.HexField(max_length=64)),
                ('uncle_hashes', django.contrib.postgres.fields.ArrayField(base_field=hub20.apps.blockchain.fields.HexField(max_length=64), size=None)),
            ],
            options={
                'unique_together': {('chain', 'hash', 'number')},
            },
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hash', hub20.apps.blockchain.fields.HexField(db_index=True, max_length=64)),
                ('from_address', hub20.apps.blockchain.fields.EthereumAddressField(db_index=True)),
                ('to_address', hub20.apps.blockchain.fields.EthereumAddressField(db_index=True, null=True)),
                ('gas', hub20.apps.blockchain.fields.Uint256Field()),
                ('gas_price', hub20.apps.blockchain.fields.Uint256Field()),
                ('nonce', hub20.apps.blockchain.fields.Uint256Field()),
                ('index', hub20.apps.blockchain.fields.Uint256Field()),
                ('value', hub20.apps.blockchain.fields.Uint256Field()),
                ('data', models.TextField()),
                ('block', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='blockchain.Block')),
            ],
        ),
        migrations.CreateModel(
            name='TransactionLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('index', models.SmallIntegerField()),
                ('data', models.TextField()),
                ('topics', django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), size=None)),
                ('transaction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='blockchain.Transaction')),
            ],
            options={
                'unique_together': {('transaction', 'index')},
            },
        ),
    ]
