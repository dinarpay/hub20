from django.dispatch import Signal

block_data_received = Signal(providing_args=["chain_id", "block_data", "transactions"])
block_sealed = Signal(providing_args=["block"])
chain_status_synced = Signal(providing_args=["chain_id", "current_block", "synced"])
chain_reorganization_detected = Signal(providing_args=["chain_id", "new_block_height"])
ethereum_node_sync_lost = Signal(providing_args=["chain"])
ethereum_node_sync_recovered = Signal(providing_args=["chain", "block_height"])
ethereum_node_disconnected = Signal(providing_args=["chain"])
ethereum_node_connected = Signal(providing_args=["chain"])
transaction_broadcast = Signal(providing_args=["chain_id", "transaction_data"])
transaction_mined = Signal(providing_args=["chain_id", "transaction_receipt", "block_data"])
