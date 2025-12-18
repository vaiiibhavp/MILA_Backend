from typing import Dict, Any, Optional, Tuple
from core.utils.helper import get_membership_period
from core.utils.response_mixin import CustomResponseMixin
from services.translation import translate_message
from tronpy import Tron
import requests, base58, hashlib
from config.basic_config import settings
from schemas.transcation_schema import PaymentDetailsModel, TransactionCreateModel, TransactionUpdateModel
from core.utils.core_enums import MembershipType, MembershipStatus, TokenTransactionType, TokenTransactionReason, TransactionStatus
from config.db_config import transaction_collection, system_config_collection, user_collection
from config.models.transaction_models import store_transaction_details, update_transaction_details
from bson import ObjectId
from config.models.user_token_history_model import create_user_token_history
from schemas.user_token_history_schema import CreateTokenHistory

client = Tron(network=settings.WALLET_NETWORK)
response = CustomResponseMixin()
TRONGRID = "https://api.trongrid.io"

def hex20_to_base58(hex20: str) -> str:
    """Convert 20-byte hex (no 0x) to Tron base58 address (T...)."""
    if hex20.startswith("0x"):
        hex20 = hex20[2:]
    # prefix 0x41 then checksum like base58check (double SHA256)
    payload = bytes.fromhex("41" + hex20)
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    addr = base58.b58encode(payload + checksum).decode()
    return addr

def decode_trc20_input(data_hex: str):
    """Decode TRC20 transfer ABI input (transfer(address,uint256))."""
    if data_hex.startswith("0x"):
        data_hex = data_hex[2:]
    data_hex = data_hex.lower()
    method = data_hex[:8]
    if method != "a9059cbb":
        return None
    to_slot = data_hex[8:8+64]
    amount_slot = data_hex[8+64:8+64+64]
    to_hex20 = to_slot[-40:]
    amount_units = int(amount_slot, 16)
    to_base58 = hex20_to_base58(to_hex20)
    return {"to_hex20": to_hex20, "to": to_base58, "amount_units": amount_units}

def fetch_with_rpc(txid: str):
    """Fallback: use TronGrid HTTP endpoints directly (no tronpy)."""
    r1 = requests.post(f"{TRONGRID}/wallet/gettransactionbyid", json={"value": txid})
    raw = r1.json()
    r2 = requests.post(f"{TRONGRID}/wallet/gettransactioninfobyid", json={"value": txid})
    info = r2.json()
    return raw, info

def fetch_token_metadata(contract_addr_hex58: str):
    # use v1 contract endpoint to read token metadata (if verified)
    # contract_addr_hex58 is like TX... or T..., Tronscan uses contract address in base58 (T...)
    url = f"{TRONGRID}/v1/contracts/{contract_addr_hex58}"
    print(f"Fetching metadata for {url}")
    r = requests.get(url)
    # keys: abi, decimals, name, symbol (may be under "trc20" / "abi" depending response)
    # Try common fields:
    token = {}
    if r.status_code != 200:
        usdt = client.get_contract(contract_addr_hex58)
        name = usdt.functions.name()
        symbol = usdt.functions.symbol()
        decimals = usdt.functions.decimals()
        token["name"] = name
        token["symbol"] = symbol
        token["decimals"] = int(decimals)
        print("usdt contract info --------", name, symbol, decimals)
        return token
    j = r.json()

    if "data" in j and isinstance(j["data"], dict):
        d = j["data"]
        token["name"] = d.get("name") or d.get("tokenName")
        token["symbol"] = d.get("symbol") or d.get("tokenSymbol")
        token["decimals"] = int(d.get("decimals")) if d.get("decimals") not in (None, "") else None
    else:
        token["name"] = j.get("name")
        token["symbol"] = j.get("symbol")
        token["decimals"] = int(j["decimals"]) if j.get("decimals") not in (None, "") else None
    # fallback: try to call decimals() via tronpy/rpc if None (not implemented here)
    return token

async def get_transaction_details(txn_id:str, lang:str) -> dict:

    try:

        tx_details = client.get_transaction(txn_id)
        tx_info = client.get_transaction_info(txn_id)
    except Exception as e:
        tx_details, tx_info = None, None

    if not tx_details:
        tx_details, tx_info = fetch_with_rpc(txn_id)

    # tx_details structure: look into raw_data.contract[].parameter.value
    contracts = tx_details.get("raw_data", {}).get("contract", [])

    parsed = {
        "txid": txn_id,
        "status": None,
        "from": None,
        "contract_address": None,
        "is_trc20": False,
        "to": None,
        "amount_units": None,
        "amount": None,
        "token": None,
        "tx_info": tx_info,
    }

    # get status/result from tx_info if available
    if tx_info:
        # common fields: receipt.result / result
        if isinstance(tx_info, dict):
            # tronpy returns python objects sometimes; be defensive
            receipt = tx_info.get("receipt") or tx_info
            result = None
            if isinstance(receipt, dict):
                result = receipt.get("result") or receipt.get("receipt", {}).get("result")
            parsed["status"] = result or tx_info.get("result") or None

    # parse contracts
    for c in contracts:
        ctype = c.get("type")
        param = c.get("parameter", {}).get("value", {}) or {}
        # For TriggerSmartContract the payload data is in param.data and contract_address is the token
        data_hex = param.get("data") or param.get("input")
        contract_addr = param.get("contract_address") or param.get("contractAddress")

        owner = param.get("owner_address") or param.get("ownerAddress")
        if owner:
            parsed["from"] = owner
        if contract_addr:
            parsed["contract_address"] = contract_addr

        if data_hex:
            dec = decode_trc20_input(data_hex)
            if dec:
                parsed["is_trc20"] = True
                parsed["to"] = dec["to"]
                parsed["amount_units"] = dec["amount_units"]
                # fetch token metadata (symbol, decimals)
                # contract_addr might be hex or base58; ensure base58 for v1 API:
                contract_base58 = contract_addr
                # tron RPC might return contract address in hex (starts with 41...), detect:
                if contract_addr and contract_addr.startswith("41"):
                    # hex to base58
                    contract_base58 = hex20_to_base58(contract_addr[2:])  # drop 41
                token_meta = fetch_token_metadata(contract_base58)
                if token_meta and token_meta.get("decimals") is not None:
                    parsed["amount"] = parsed["amount_units"] / (10 ** int(token_meta["decimals"]))
                else:
                    parsed["amount"] = None
                break
    if parsed is None or parsed['status'] is None:
        raise response.raise_exception(translate_message("ERROR_WHILE_FETCHING_TRANSACTION_DETAILS", lang=lang),
                                       data=[], status_code=502)
    return parsed

def validate_destination_wallet(
    wallet_address: str,
    lang: str,
) -> Optional[Any]:
    if wallet_address != settings.ADMIN_WALLET_ADDRESS:
        raise response.raise_exception(translate_message("INVALID_DESTINATION_WALLET", lang=lang),data=[])
    return None

def validate_transaction_status(
    transaction_status,
    lang: str,
) -> Optional[Any]:
    if transaction_status.lower() != "success":
        raise response.raise_exception(translate_message("TRANSACTION_NOT_SUCCESSFUL", lang=lang), data=[])
    return None

async def build_transaction_model(
    user_id: str,
    plan_data: Dict[str, Any],
    transaction_details: Dict[str, Any],
    partial_payment_data: Dict[str, Any] = None,
) -> TransactionCreateModel:
    plan_amount = float(plan_data["amount"])
    paid_amount = float(transaction_details["amount"])
    remaining_amount = plan_amount - paid_amount
    if partial_payment_data is not None:
        paid_amount = partial_payment_data['paid_amount'] + float(transaction_details["amount"])
        remaining_amount = partial_payment_data['plan_amount'] - paid_amount

    payment_details = PaymentDetailsModel(**transaction_details)

    status = (
        TransactionStatus.SUCCESS.value
        if plan_amount <= paid_amount
        else TransactionStatus.PARTIAL.value
    )

    return TransactionCreateModel(
        user_id=user_id,
        plan_id=str(plan_data["_id"]),
        plan_amount=plan_amount,
        paid_amount=paid_amount,
        remaining_amount=remaining_amount,
        status=status,
        payment_details=payment_details,
    )

async def handle_full_payment(
    transaction_data: TransactionCreateModel,
    plan_data: Dict[str, Any],
    user_id: str,
) -> Dict[str, Any]:
    """
    Handles membership period, token credit, and user membership updates
    for fully paid transactions.
    """

    transaction_data, system_config = await _prepare_transaction_for_subscription(
        transaction_data=transaction_data,
        plan_data=plan_data,
        user_id=user_id
    )
    user_details = await user_collection.find_one({"_id": ObjectId(user_id)})
    on_subscribe_tokens = int(system_config["on_subscribe_token"])
    transaction_data.tokens = on_subscribe_tokens

    # 3. Persist transaction
    doc = await store_transaction_details(transaction_data)

    # 4. Token history and membership updates
    await _update_user_membership_and_tokens(
        user_id=user_id,
        user_details=user_details,
        on_subscribe_tokens=on_subscribe_tokens,
        transaction_id=doc["_id"],
    )

    return doc

async def _calculate_membership_period_for_user(
    plan_data: Dict[str, Any],
    user_id: str,
) -> Tuple[Any, Any]:
    """
    Calculates membership start and expiry dates.
    Extends existing membership if current membership is active.
    """

    validity_value = int(plan_data["validity_value"])
    validity_unit = plan_data["validity_unit"]

    # Default: new membership period from now
    start_date, expiry_date = get_membership_period(validity_value, validity_unit)

    user_details = await user_collection.find_one({"_id": ObjectId(user_id)})
    membership_status = user_details.get("membership_status", MembershipStatus.EXPIRED)

    # If user already has active membership, extend from current expiry
    if membership_status == MembershipStatus.ACTIVE.value:
        current_mem_txn_id = user_details.get("membership_trans_id")
        if current_mem_txn_id:
            current_mem_txn_details = await transaction_collection.find_one(
                {"_id": ObjectId(current_mem_txn_id)}
            )
            if current_mem_txn_details:
                _, expiry_date = get_membership_period(
                    validity_value,
                    validity_unit,
                    current_mem_txn_details["expires_at"],
                )
                # If extending, start_date can be same as previous expiry
                start_date = current_mem_txn_details["expires_at"]

    return start_date, expiry_date


async def _update_user_membership_and_tokens(
    user_id: str,
    user_details: Dict[str, Any],
    on_subscribe_tokens: int,
    transaction_id: ObjectId,
) -> None:
    """
    Handles token balance, token history, and membership fields on the user document.
    """

    membership_status = user_details.get("membership_status", MembershipStatus.EXPIRED)
    current_tokens = int(user_details.get("tokens") or 0)
    new_balance = current_tokens + on_subscribe_tokens

    # Record token history (always, even if already active)
    token_history_data = CreateTokenHistory(
        user_id=str(ObjectId(user_id)),
        delta=on_subscribe_tokens,
        type=TokenTransactionType.CREDIT.value,
        reason=TokenTransactionReason.SUBSCRIPTION.value,
        balance_before=str(current_tokens),
        balance_after=str(new_balance),
    )
    await create_user_token_history(data=token_history_data)

    # If already active, don't change membership status / type / trans_id
    if membership_status == MembershipStatus.ACTIVE.value:
        await user_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"tokens": str(new_balance)}},
        )
        return

    # Activate membership for non-active users
    await user_collection.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "tokens": str(new_balance),
                "membership_type": MembershipType.PREMIUM.value,
                "membership_status": MembershipStatus.ACTIVE.value,
                "membership_trans_id": transaction_id,
            }
        },
    )

async def _prepare_transaction_for_subscription(
    transaction_data: TransactionCreateModel,
    user_id: str,
    plan_data: Dict[str, Any],
) -> Tuple[TransactionCreateModel,dict]:
    """
        Prepare transaction_data for a new subscription:
          1. calculate membership period (may extend existing membership)
          2. set start_date and expires_at on transaction_data
          3. fetch system_config
          4. set transaction_data.tokens from system_config

        Returns:
          (transaction_data, system_config)
    """
    # 1. Determine membership period (may extend current membership)
    start_date, expiry_date = await _calculate_membership_period_for_user(
        plan_data=plan_data,
        user_id=user_id,
    )

    transaction_data.start_date = start_date
    transaction_data.expires_at = expiry_date

    # 2. Fetch system config and user
    system_config = await system_config_collection.find_one()

    on_subscribe_tokens = int(system_config["on_subscribe_token"])
    transaction_data.tokens = on_subscribe_tokens
    return transaction_data, system_config

async def mark_full_payment_received(
    transaction_data: TransactionCreateModel,
    plan_data: Dict[str, Any],
    user_id: str,
    subscription_id:str
) -> Dict[str, Any]:
    """
        Handles membership period, token credit, and user membership updates
        for remaining paid transactions.
    """
    transaction_data, system_config = await _prepare_transaction_for_subscription(
        transaction_data = transaction_data,
        plan_data = plan_data,
        user_id = user_id
    )
    user_details = await user_collection.find_one({"_id": ObjectId(user_id)})
    on_subscribe_tokens = int(system_config["on_subscribe_token"])
    transaction_data.tokens = on_subscribe_tokens

    # 3. Persist transaction
    doc = await update_transaction_details(doc=TransactionUpdateModel(**transaction_data.model_dump()),subscription_id=subscription_id)

    # 4. Token history and membership updates
    await _update_user_membership_and_tokens(
        user_id=user_id,
        user_details=user_details,
        on_subscribe_tokens=on_subscribe_tokens,
        transaction_id=doc["_id"],
    )

    return doc



