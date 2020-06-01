from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from hub20.apps.blockchain.factories import BlockFactory, TransactionFactory
from hub20.apps.ethereum_money.factories import ETHFactory
from hub20.apps.ethereum_money.models import EthereumTokenAmount, encode_transfer_data
from hub20.apps.ethereum_wallet.factories import WalletFactory
from hub20.apps.ethereum_wallet.models import Wallet
from hub20.apps.ethereum_wallet.tests.base import add_eth_to_wallet, add_token_to_wallet
from hub20.apps.raiden.factories import ChannelFactory, PaymentEventFactory, TokenNetworkFactory

from ..choices import TRANSFER_EVENT_TYPES
from ..factories import (
    CheckoutFactory,
    Erc20TokenPaymentOrderFactory,
    Erc20TokenUserBalanceEntryFactory,
    ExternalTransferFactory,
    InternalTransferFactory,
    StoreFactory,
    UserAccountFactory,
)
from ..models import BlockchainPaymentRoute, ExternalTransfer, RaidenPaymentRoute, UserAccount
from ..settings import app_settings


@pytest.mark.django_db(transaction=True)
class BaseTestCase(TestCase):
    pass


class BlockchainPaymentTestCase(BaseTestCase):
    def setUp(self):
        self.order = Erc20TokenPaymentOrderFactory()
        self.blockchain_route = BlockchainPaymentRoute.objects.filter(order=self.order).first()

    def test_transaction_sets_payment_as_received(self):
        add_token_to_wallet(
            self.blockchain_route.wallet, self.order.as_token_amount, self.order.chain
        )
        self.assertTrue(self.order.is_paid)
        self.assertFalse(self.order.is_confirmed)

    def test_transaction_creates_blockchain_payment(self):
        add_token_to_wallet(
            self.blockchain_route.wallet, self.order.as_token_amount, self.order.chain
        )
        self.assertEqual(self.order.payments.count(), 1)

    def test_user_balance_is_updated_on_completed_payment(self):
        tx = add_token_to_wallet(
            self.blockchain_route.wallet, self.order.as_token_amount, self.order.chain
        )
        self.order.chain.highest_block = (
            tx.block.number + app_settings.Payment.minimum_confirmations
        )
        self.order.chain.save()
        BlockFactory.create_batch(
            app_settings.Payment.minimum_confirmations, chain=self.order.chain
        )

        user_account = UserAccount(self.order.user)
        balance = user_account.get_balance(self.order.currency)
        self.assertEqual(balance.amount, self.order.amount)


class CheckoutTestCase(BaseTestCase):
    def setUp(self):
        self.checkout = CheckoutFactory()
        self.checkout.store.accepted_currencies.add(self.checkout.currency)

    def test_checkout_user_and_store_owner_are_the_same(self):
        self.assertEqual(self.checkout.store.owner, self.checkout.user)

    def test_checkout_currency_must_be_accepted_by_store(self):
        self.checkout.clean()

        self.checkout.store.accepted_currencies.clear()
        with self.assertRaises(ValidationError):
            self.checkout.clean()


class RaidenPaymentTestCase(BaseTestCase):
    def setUp(self):
        token_network = TokenNetworkFactory()

        self.channel = ChannelFactory(token_network=token_network)
        self.channel.raiden.token_networks.add(token_network)

        self.order = Erc20TokenPaymentOrderFactory(currency=token_network.token)
        self.raiden_route = RaidenPaymentRoute.objects.filter(order=self.order).first()

    def test_order_has_raiden_route(self):
        self.assertIsNotNone(self.raiden_route)

    def test_payment_via_raiden_sets_order_as_paid(self):
        PaymentEventFactory(
            channel=self.channel,
            amount=self.order.amount,
            identifier=self.raiden_route.identifier,
            receiver_address=self.channel.raiden.address,
        )
        self.assertTrue(self.order.is_paid)


class StoreTestCase(BaseTestCase):
    def setUp(self):
        self.store = StoreFactory()

    def test_store_rsa_keys_are_valid_pem(self):
        self.assertIsNotNone(self.store.rsa.pk)
        self.assertTrue(type(self.store.rsa.public_key_pem) is str)
        self.assertTrue(type(self.store.rsa.private_key_pem) is str)

        self.assertTrue(self.store.rsa.public_key_pem.startswith("-----BEGIN PUBLIC KEY-----"))
        self.assertTrue(
            self.store.rsa.private_key_pem.startswith("-----BEGIN RSA PRIVATE KEY-----")
        )


class TransferTestCase(BaseTestCase):
    def setUp(self):
        self.sender_account = UserAccountFactory()
        self.receiver_account = UserAccountFactory()
        self.sender = self.sender_account.user
        self.receiver = self.receiver_account.user
        self.credit = Erc20TokenUserBalanceEntryFactory(user=self.sender)


class InternalTransferTestCase(TransferTestCase):
    def test_transfers_are_finalized_as_confirmed(self):
        transfer = InternalTransferFactory(
            sender=self.sender,
            receiver=self.receiver,
            currency=self.credit.currency,
            amount=self.credit.amount,
        )

        self.assertTrue(transfer.is_finalized)
        self.assertEqual(transfer.status, TRANSFER_EVENT_TYPES.confirmed)

    def test_transfers_change_balance(self):
        transfer = InternalTransferFactory(
            sender=self.sender,
            receiver=self.receiver,
            currency=self.credit.currency,
            amount=self.credit.amount,
        )

        self.assertTrue(transfer.is_finalized)

        sender_balance = self.sender_account.get_balance(self.credit.currency)
        receiver_balance = self.receiver_account.get_balance(self.credit.currency)

        self.assertEqual(sender_balance.amount, 0)
        self.assertEqual(receiver_balance, self.credit.as_token_amount)

    def test_transfers_fail_with_low_sender_balance(self):
        transfer = InternalTransferFactory(
            sender=self.sender,
            receiver=self.receiver,
            currency=self.credit.currency,
            amount=2 * self.credit.amount,
        )

        self.assertTrue(transfer.is_finalized)
        self.assertEqual(transfer.status, TRANSFER_EVENT_TYPES.failed)


@patch("hub20.apps.core.models.transfers.Wallet.select_for_transfer")
class ExternalTransferTestCase(TransferTestCase):
    def setUp(self):
        super().setUp()
        self.ETH = ETHFactory()
        self.fee_amount = EthereumTokenAmount(amount=Decimal("0.001"), currency=self.ETH)

    def _build_transfer(self, wallet: Wallet) -> ExternalTransfer:
        transfer = ExternalTransferFactory.build(
            sender=self.sender, currency=self.credit.currency, amount=self.credit.amount
        )

        out_tx = TransactionFactory(
            from_address=wallet.address,
            to_address=self.credit.currency.address,
            data=encode_transfer_data(transfer.recipient_address, self.credit.as_token_amount),
        )

        with patch.object(wallet.account, "send", return_value=out_tx.hash):
            transfer.save()

        return transfer

    def test_external_transfers_fail_without_funds(self, select_for_transfer):
        select_for_transfer.return_value = None
        transfer = ExternalTransferFactory(
            sender=self.sender, currency=self.credit.currency, amount=self.credit.amount
        )

        self.assertIsNotNone(transfer.status)
        self.assertEqual(transfer.status, TRANSFER_EVENT_TYPES.failed)

    def test_transfers_can_be_executed_with_enough_balance(self, select_for_transfer):
        wallet = WalletFactory()
        add_token_to_wallet(wallet, self.credit.as_token_amount, self.ETH.chain)
        add_eth_to_wallet(wallet, self.fee_amount, self.ETH.chain)

        select_for_transfer.return_value = wallet

        transfer = self._build_transfer(wallet)

        self.assertIsNotNone(transfer.status)
        self.assertFalse(transfer.is_finalized)
        self.assertEqual(transfer.status, TRANSFER_EVENT_TYPES.executed)

    def test_transfers_are_confirmed_after_block_confirmation(self, select_for_transfer):
        wallet = WalletFactory()

        add_eth_to_wallet(wallet, self.fee_amount, self.ETH.chain)
        add_token_to_wallet(wallet, self.credit.as_token_amount, self.ETH.chain)
        select_for_transfer.return_value = wallet

        transfer = self._build_transfer(wallet)

        self.assertIsNotNone(transfer.status)
        self.assertFalse(transfer.is_finalized)
        self.assertEqual(transfer.status, TRANSFER_EVENT_TYPES.executed)

        self.ETH.chain.highest_block = app_settings.Transfer.minimum_confirmations
        self.ETH.chain.save()
        BlockFactory.create_batch(
            app_settings.Transfer.minimum_confirmations, chain=self.ETH.chain
        )
        self.assertTrue(transfer.is_finalized)
        self.assertEqual(transfer.status, TRANSFER_EVENT_TYPES.confirmed)


__all__ = [
    "BlockchainPaymentTestCase",
    "CheckoutTestCase",
    "RaidenPaymentTestCase",
    "StoreTestCase",
    "TransferTestCase",
    "InternalTransferTestCase",
    "ExternalTransferTestCase",
]
