import datetime
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from blockchain.models import Block, Transaction
from ethereum_money.signals import account_deposit_received
from raiden.models import Raiden, Payment as RaidenPaymentEvent
from raiden.signals import raiden_payment_received
from hub20.app_settings import PAYMENT_SETTINGS, TRANSFER_SETTINGS
from hub20.choices import PAYMENT_EVENT_TYPES, TRANSFER_EVENT_TYPES
from hub20.models import (
    PaymentOrder,
    PaymentOrderMethod,
    BlockchainPayment,
    RaidenPayment,
    InternalPayment,
    PaymentOrderEvent,
    InternalTransfer,
    Transfer,
    ExternalTransfer,
    Wallet,
)
from hub20.signals import (
    payment_received,
    payment_confirmed,
    order_paid,
    transfer_confirmed,
    transfer_executed,
    transfer_failed,
    transfer_scheduled,
)
from hub20.tasks import execute_transfer

logger = logging.getLogger(__name__)


@receiver(account_deposit_received, sender=Transaction)
def on_account_deposit_check_blockchain_payments(sender, **kw):
    account = kw["account"]
    transaction = kw["transaction"]
    amount = kw["amount"]

    order = PaymentOrder.objects.filter(payment_method__wallet__account=account).first()

    if not order:
        return

    payment = BlockchainPayment.objects.create(
        order=order, amount=amount.amount, currency=amount.currency, transaction=transaction,
    )
    payment_received.send(sender=BlockchainPayment, payment=payment)


@receiver(raiden_payment_received, sender=RaidenPaymentEvent)
def on_raiden_payment_received_check_raiden_payments(sender, **kw):
    raiden_payment = kw["payment"]

    order = PaymentOrder.objects.filter(
        payment_method__identifier=raiden_payment.identifier,
        payment_method__raiden=raiden_payment.channel.raiden,
    ).first()

    if order is not None:
        amount = raiden_payment.as_token_amount
        payment = RaidenPayment.objects.create(
            order=order,
            amount=amount.amount,
            currency=raiden_payment.token,
            payment=raiden_payment,
        )
        payment_confirmed.send(sender=RaidenPayment, payment=payment)


@receiver(post_save, sender=PaymentOrder)
def on_order_created_set_payment_methods(sender, **kw):
    order = kw["instance"]
    if kw["created"]:
        unlocked_wallets = Wallet.objects.filter(paymentordermethod__isnull=True)
        wallet = unlocked_wallets.order_by("?").first() or Wallet.generate()

        raiden = Raiden.objects.filter(token_networks__token=order.currency).first()
        expiration_time = order.created + datetime.timedelta(
            seconds=PaymentOrderMethod.EXPIRATION_TIME
        )

        PaymentOrderMethod.objects.create(
            order=order, wallet=wallet, raiden=raiden, expiration_time=expiration_time
        )


@receiver(post_save, sender=PaymentOrder)
def on_payment_created_set_created_status(sender, **kw):
    payment = kw["instance"]
    if payment.created:
        payment.events.create(status=PAYMENT_EVENT_TYPES.requested)


@receiver(post_save, sender=PaymentOrderEvent)
def on_payment_event_created_send_order_paid_signal(sender, **kw):
    payment_event = kw["instance"]
    if payment_event.created and payment_event.status == PAYMENT_EVENT_TYPES.confirmed:
        order_paid.send(sender=PaymentOrder, payment_order=payment_event.order)


@receiver(post_save, sender=Block)
def on_block_added_check_confirmed_payments(sender, **kw):
    block = kw["instance"]
    created = kw["created"]

    block_number_to_confirm = block.number - PAYMENT_SETTINGS.minimum_confirmations
    if created and block_number_to_confirm >= 0:
        logger.info(f"Block {block} created")

        payments = BlockchainPayment.objects.all()

        for payment in payments.filter(
            transaction__block__number=block_number_to_confirm,
            transaction__block__chain=block.chain,
        ):
            logger.info(f"Confirming {payment}")
            payment_confirmed.send(sender=BlockchainPayment, payment=payment)


@receiver(post_save, sender=Block)
def on_block_added_check_confirmed_transfers(sender, **kw):
    block = kw["instance"]
    created = kw["created"]

    block_number_to_confirm = block.number - TRANSFER_SETTINGS.minimum_confirmations
    if created and block_number_to_confirm >= 0:
        logger.info(f"Block {block} created")

        transactions = Transaction.objects.filter(
            block__number=block_number_to_confirm, block__chain=block.chain
        )

        tx_hashes = transactions.values_list("hash", flat=True)
        transfers = ExternalTransfer.objects.all()
        for transfer in transfers.filter(chain_transaction__transaction_hash__in=tx_hashes):
            logger.info(f"Confirming {transfer}")
            transfer_confirmed.send(sender=ExternalTransfer, transfer=transfer)


@receiver(payment_received, sender=InternalPayment)
@receiver(payment_received, sender=BlockchainPayment)
def on_payment_received_update_status(sender, **kw):
    payment = kw["payment"]
    logger.info(f"Processing payment {payment} received")
    payment.order.update_status()
    payment.order.maybe_finalize()


@receiver(payment_confirmed, sender=BlockchainPayment)
@receiver(payment_confirmed, sender=RaidenPayment)
def on_payment_confirmed_finalize(sender, **kw):
    payment = kw["payment"]
    logger.info(f"Processing payment {payment} confirmed")
    payment.order.maybe_finalize()


@receiver(order_paid, sender=PaymentOrder)
def on_order_paid_credit_user(sender, **kw):
    order = kw["payment_order"]

    order.user.balance_entries.create(amount=order.amount, currency=order.currency)


@receiver(order_paid, sender=PaymentOrder)
def on_order_paid_free_payment_channels(sender, **kw):
    order = kw["payment_order"]

    if order.payment_method:
        order.payment_method.delete()


@receiver(post_save, sender=InternalTransfer)
@receiver(post_save, sender=ExternalTransfer)
def on_transfer_created_mark_transfer_scheduled(sender, **kw):
    transfer = kw["instance"]
    if kw["created"]:
        transfer.events.create(status=TRANSFER_EVENT_TYPES.scheduled)
        execute_transfer.delay(transfer.id)
        transfer_scheduled.send(sender=sender, transfer=transfer)


@receiver(transfer_failed, sender=Transfer)
def on_transfer_failed_mark_as_failed(sender, **kw):
    transfer = kw["transfer"]
    transfer.events.create(status=TRANSFER_EVENT_TYPES.failed)


@receiver(transfer_confirmed, sender=ExternalTransfer)
@receiver(transfer_confirmed, sender=InternalTransfer)
def on_transfer_confirmed_mark_as_confirmed(sender, **kw):
    transfer = kw["transfer"]
    transfer.events.create(status=TRANSFER_EVENT_TYPES.confirmed)


@receiver(transfer_executed, sender=ExternalTransfer)
def on_external_transfer_executed_mark_as_executed(sender, **kw):
    transfer = kw["transfer"]
    transfer.events.create(status=TRANSFER_EVENT_TYPES.executed)


@receiver(transfer_confirmed, sender=ExternalTransfer)
def on_external_transfer_confirmed_destroy_reserve(sender, **kw):
    transfer = kw["transfer"]
    try:
        transfer.reserve.delete()
    except Transfer.reserve.RelatedObjectDoesNotExist:
        pass
    except Exception as exc:
        logger.exception(exc)


@receiver(transfer_confirmed, sender=InternalTransfer)
def on_internal_transfer_confirmed_move_balances(sender, **kw):
    transfer = kw["transfer"]
    transfer.receiver.balance_entries.create(amount=transfer.amount, currency=transfer.currency)
    transfer.sender.balance_entries.create(amount=-transfer.amount, currency=transfer.currency)


__all__ = [
    "on_account_deposit_check_blockchain_payments",
    "on_block_added_check_confirmed_payments",
    "on_block_added_check_confirmed_transfers",
    "on_payment_created_set_created_status",
    "on_payment_event_created_send_order_paid_signal",
    "on_payment_received_update_status",
    "on_payment_confirmed_finalize",
    "on_order_paid_credit_user",
    "on_order_paid_free_payment_channels",
    "on_order_created_set_payment_methods",
    "on_transfer_created_mark_transfer_scheduled",
    "on_transfer_failed_mark_as_failed",
    "on_transfer_confirmed_mark_as_confirmed",
    "on_internal_transfer_confirmed_move_balances",
    "on_external_transfer_executed_mark_as_executed",
    "on_external_transfer_confirmed_destroy_reserve",
]
