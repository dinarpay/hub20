import factory
from factory import fuzzy

from hub20.apps.blockchain.factories import (
    EthereumProvider,
    SyncedChainFactory,
    TransactionFactory,
)
from hub20.apps.core import models
from hub20.apps.ethereum_money.factories import Erc20TokenFactory, ETHFactory

from .base import UserFactory

factory.Faker.add_provider(EthereumProvider)


class PaymentOrderFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    amount = fuzzy.FuzzyDecimal(0, 10, precision=6)
    chain = factory.SubFactory(SyncedChainFactory)

    class Meta:
        abstract = False
        model = models.PaymentOrder


class ETHPaymentOrderFactory(PaymentOrderFactory):
    currency = factory.SubFactory(ETHFactory)

    class Meta:
        model = models.PaymentOrder


class Erc20TokenPaymentOrderFactory(PaymentOrderFactory):
    currency = factory.SubFactory(Erc20TokenFactory)

    class Meta:
        model = models.PaymentOrder


class BlockchainPaymentRouteFactory(factory.django.DjangoModelFactory):
    order = factory.SubFactory(ETHPaymentOrderFactory)

    class Meta:
        model = models.BlockchainPaymentRoute


class BlockchainPaymentFactory(factory.django.DjangoModelFactory):
    route = factory.SubFactory(BlockchainPaymentRouteFactory)
    transaction = factory.SubFactory(TransactionFactory)

    class Meta:
        model = models.BlockchainPayment


class PendingBlockchainPaymentFactory(BlockchainPaymentFactory):
    transaction_hash = factory.Faker("hex64")


__all__ = [
    "ETHPaymentOrderFactory",
    "Erc20TokenPaymentOrderFactory",
    "BlockchainPaymentFactory",
    "PendingBlockchainPaymentFactory",
]
