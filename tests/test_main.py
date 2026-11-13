import pytest
import sys
import os
import json
import hashlib
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from datetime import date, datetime, timedelta
from models import BankAccount, SavingsAccount, PremiumAccount, InvestmentAccount, Client, Bank, Transaction, TransactionQueue, TransactionProcessor, AuditLog, AuditEntry, AuditLevel,RiskAnalyzer,RiskLevel, RiskEvent, AuditReporter
from utils import (
    ClientNotAdultError, ClientBlockedError, AuthenticationError,
    RestrictedTimeError, AccountNotFoundError, ClientNotAdultError, AccountClosedError,
    AccountFrozenError, InvalidOperationError, InsufficientFundsError, validate_amount, ClientNotFoundError
)
from currency_converter import CurrencyConverter

#test for day1
def test_deposit_valid():
    acc = BankAccount("Test User", balance=100.0)
    acc.deposit(50.0)
    assert acc.balance == 150.0
def test_withdraw_valid():
    acc = BankAccount("Test User", balance=100.0)
    acc.withdraw(40.0)
    assert acc.balance == 60.0

def test_negative_amount():
    acc = BankAccount("Test User", balance=100.0)
    with pytest.raises(InvalidOperationError):
        acc.deposit(-10.0)
    with pytest.raises(InvalidOperationError):
        acc.withdraw(-10.0)

def test_insufficient_funds():
    acc = BankAccount("Test User", balance=100.0)
    with pytest.raises(InsufficientFundsError):
        acc.withdraw(150.0)

def test_frozen_account():
    acc = BankAccount("Test User")
    acc.status = "frozen"
    with pytest.raises(AccountFrozenError):
        acc.deposit(10.0)


def test_closed_account():
    acc = BankAccount("Test User")
    acc.status = "closed"
    with pytest.raises(AccountClosedError):
        acc.withdraw(10.0)

def test_invalid_currency():
    with pytest.raises(InvalidOperationError):
        BankAccount("Test User", currency="GBP")

def test_str_representation():
    acc = BankAccount("Иван", account_id="12345678", balance=100, currency="EUR")
    acc_str = str(acc)
    assert "***5678" in acc_str
    assert "Иван" in acc_str
    assert "ACTIVE" in acc_str
    assert "100 EUR" in acc_str

#tests for day2
def test_savings_account_min_balance():
    acc = SavingsAccount("test", balance=1000.0, min_balance=500.0)
    with pytest.raises(InvalidOperationError):
        acc.withdraw(600.0)
    acc.withdraw(300.0)
    assert acc.balance == 700.0

def test_savings_interest():
    acc = SavingsAccount("Test", balance=1000.0, interest_rate=0.10)
    acc.apply_monthly_interest()
    assert acc.balance == 1100.0
    
def test_premium_overdraft_and_commission():
    acc = PremiumAccount("test", balance=1000.0, overdraft_limit=500.0, commission=50.0)
    acc.withdraw(1000.0)
    assert acc.balance == -50.0
    
    with pytest.raises(InsufficientFundsError):
        acc.withdraw(500.0)

def test_investment_account():
    acc = InvestmentAccount("Test", balance=5000.0)
    
    acc.invest("stocks", 1000.0)
    acc.invest("bonds", 500.0)

    assert acc.balance == 3500.0
    assert acc.portfolio["stocks"] == 1000.0
    assert acc.portfolio["bonds"] == 500.0

    with pytest.raises(InvalidOperationError):
        acc.invest("crypto", 100.0)

    with pytest.raises(InsufficientFundsError):
        acc.invest("etf", 10000.0)

    rates = {"stocks": 0.10, "bonds": 0.04, "etf": 0.07}
    projected = acc.project_yearly_growth(rates)
    assert projected == 1620.0

#tests for day3

@pytest.fixture
def daytime():
    return lambda: datetime(2024, 1, 1, 12, 0)

@pytest.fixture
def nighttime():
    return lambda: datetime(2024, 1, 1, 2, 0)

@pytest.fixture
def bank(daytime):
    return Bank(now_provider=daytime)

@pytest.fixture
def anna():
    return Client("Анна Смирнова", date(1990, 5, 15), {"phone": "+7..."}, "anna_pass")

@pytest.fixture
def oleg():
    return Client("Олег Петров", date(1985, 9, 1), {"phone": "+7..."}, "oleg_pass")
def test_client_minor_raises():
    with pytest.raises(ClientNotAdultError):
        Client("Minor", date.today() - timedelta(days=365 * 10), {}, "pass")

def test_client_adult_ok(anna):
    assert anna.status == "active"
    assert anna.failed_attempts == 0
    assert anna.suspicious_activity is False

def test_add_client(bank, anna):
    cid = bank.add_client(anna)
    assert cid in bank.clients

def test_open_account(bank, anna):
    bank.add_client(anna)
    acc = bank.open_account(anna.client_id, "savings", balance=1000, min_balance=100)
    assert acc.account_id in anna.account_ids
    assert bank.accounts[acc.account_id] is acc

def test_open_unknown_type(bank, anna):
    bank.add_client(anna)
    with pytest.raises(InvalidOperationError):
        bank.open_account(anna.client_id, "diamond")

# ---------- Authentication ----------
def test_auth_success(bank, anna):
    bank.add_client(anna)
    assert bank.authenticate_client(anna.client_id, "anna_pass") is True

def test_auth_wrong_password(bank, anna):
    bank.add_client(anna)
    with pytest.raises(AuthenticationError):
        bank.authenticate_client(anna.client_id, "wrong")
    assert anna.failed_attempts == 1

def test_auth_three_attempts_block(bank, anna):
    bank.add_client(anna)
    for _ in range(2):
        with pytest.raises(AuthenticationError):
            bank.authenticate_client(anna.client_id, "wrong")
    with pytest.raises(ClientBlockedError):
        bank.authenticate_client(anna.client_id, "wrong")
    assert anna.status == "blocked"
    assert anna.suspicious_activity is True

def test_blocked_client_cannot_auth(bank, anna):
    bank.add_client(anna)
    anna.status = "blocked"
    with pytest.raises(ClientBlockedError):
        bank.authenticate_client(anna.client_id, "anna_pass")

# ---------- Freeze / unfreeze / close ----------
def test_freeze_unfreeze(bank, anna):
    bank.add_client(anna)
    acc = bank.open_account(anna.client_id, "basic", balance=1000)
    bank.freeze_account(acc.account_id)
    assert acc.status == "frozen"
    bank.unfreeze_account(acc.account_id)
    assert acc.status == "active"

def test_close_with_balance_raises(bank, anna):
    bank.add_client(anna)
    acc = bank.open_account(anna.client_id, "basic", balance=100)
    with pytest.raises(InvalidOperationError):
        bank.close_account(acc.account_id)

def test_close_zero_balance(bank, anna):
    bank.add_client(anna)
    acc = bank.open_account(anna.client_id, "basic", balance=0)
    bank.close_account(acc.account_id)
    assert acc.status == "closed"

# ---------- Time restriction ----------
def test_restricted_time_deposit(nighttime, anna):
    bank = Bank(now_provider=nighttime)
    bank.add_client(anna)
    # Открытие счёта днём (обход через daytime), затем ночное пополнение
    daytime_bank = Bank(now_provider=lambda: datetime(2024, 1, 1, 12, 0))
    daytime_bank.add_client(anna)
    acc = daytime_bank.open_account(anna.client_id, "basic", balance=100)

    bank.accounts = daytime_bank.accounts  # тот же счёт
    with pytest.raises(RestrictedTimeError):
        bank.deposit(anna.client_id, "anna_pass", acc.account_id, 50)

# ---------- Ownership ----------
def test_foreign_account_marks_suspicious(bank, anna, oleg):
    bank.add_client(anna); bank.add_client(oleg)
    acc_oleg = bank.open_account(oleg.client_id, "basic", balance=1000)
    with pytest.raises(InvalidOperationError):
        bank.withdraw(anna.client_id, "anna_pass", acc_oleg.account_id, 100)
    assert anna.suspicious_activity is True

# ---------- Analytics ----------
def test_total_balance(bank, anna):
    bank.add_client(anna)
    bank.open_account(anna.client_id, "basic", balance=1000, currency="RUB")
    bank.open_account(anna.client_id, "savings", balance=500, currency="RUB")
    assert bank.get_total_balance(anna.client_id) == 1500

def test_clients_ranking(bank, anna, oleg):
    bank.add_client(anna); bank.add_client(oleg)
    bank.open_account(anna.client_id, "basic", balance=100)
    bank.open_account(oleg.client_id, "basic", balance=500)
    ranking = bank.get_clients_ranking()
    assert ranking[0][0] is oleg
    assert ranking[1][0] is anna

# ---------- Search ----------
def test_search_by_owner(bank, anna):
    bank.add_client(anna)
    bank.open_account(anna.client_id, "basic", balance=100)
    assert len(bank.search_accounts("Анна")) == 1
    assert len(bank.search_accounts("нет такого")) == 0

def test_search_by_status(bank, anna):
    bank.add_client(anna)
    a1 = bank.open_account(anna.client_id, "basic", balance=0)
    a2 = bank.open_account(anna.client_id, "basic", balance=0)
    bank.freeze_account(a2.account_id)
    assert bank.search_accounts(status="active") == [a1]
    assert bank.search_accounts(status="frozen") == [a2]

#day4
def test_same_currency_no_conversion():
    conv = CurrencyConverter()
    assert conv.convert(100.0, "RUB", "RUB") == 100.0


def test_same_currency_does_not_need_rate():
    
    conv = CurrencyConverter({})  # пустой
    assert conv.convert(50.0, "RUB", "RUB") == 50.0


def test_usd_to_rub():
    conv = CurrencyConverter({("USD", "RUB"): 90.0})
    assert conv.convert(100.0, "USD", "RUB") == pytest.approx(9000.0)

def test_transaction_valid_transfer():
    tx = Transaction("transfer", 100.0, "RUB", from_account_id="a1", to_account_id="a2", commission=5.0)
    assert tx.status == "pending", tx.failure_reason is None
    assert tx.failure_code is None, tx.attempts == 0
    assert tx.id
    assert len(tx.id) == 8 

def test_transaction_transfer_requires_both_ids():
    with pytest.raises(InvalidOperationError):
        Transaction("transfer", 100, "RUB", from_account_id="a1")
    with pytest.raises(InvalidOperationError):
        Transaction("transfer", 100, "RUB", to_account_id="a2")
    with pytest.raises(InvalidOperationError):
        Transaction("transfer", 100, "RUB")

def test_transaction_self_transfer_raises():
    with pytest.raises(InvalidOperationError):
        Transaction("transfer", 100, "RUB", from_account_id="a1", to_account_id="a1")
def test_transaction_negative_commission_raises():
    with pytest.raises(InvalidOperationError):
        Transaction("transfer", 100, "RUB", from_account_id="a1", to_account_id="a2", commission = -1)

def test_total_debit_property():
    tx = Transaction("transfer", 100, "RUB", from_account_id="a1", to_account_id="a2", commission = 10)
    assert tx.total_debit == 110

NOW = lambda: datetime(2024, 1, 1, 12, 0)
def test_fifo_same_priority():
   
    t1 = Transaction("transfer", 100, "RUB",
                     from_account_id="src", to_account_id="dst",
                     commission=0, transaction_id="a",
                     priority=5, now_provider=NOW)
    t2 = Transaction("transfer", 200, "RUB",
                     from_account_id="src", to_account_id="dst",
                     commission=0, transaction_id="b",
                     priority=5, now_provider=NOW)
    t3 = Transaction("transfer", 300, "RUB",
                     from_account_id="src", to_account_id="dst",
                     commission=0, transaction_id="c",
                     priority=5, now_provider=NOW)

    q = TransactionQueue(now_provider=NOW)
    q.enqueue(t1); q.enqueue(t2); q.enqueue(t3)

    assert q.dequeue() is t1
    assert q.dequeue() is t2
    assert q.dequeue() is t3

def test_priority_order():
   
    t1 = Transaction("transfer", 100, "RUB",
                     from_account_id="src", to_account_id="dst",
                     commission=0, transaction_id="a",
                     priority=1, now_provider=NOW)
    t2 = Transaction("transfer", 200, "RUB",
                     from_account_id="src", to_account_id="dst",
                     commission=0, transaction_id="b",
                     priority=10, now_provider=NOW)
    q = TransactionQueue()
    q.enqueue(t1)
    q.enqueue(t2)
    assert q.dequeue() is t1; q.dequeue() is t2

def test_scheduled_not_ready_returns_none():
    q = TransactionQueue(now_provider=lambda: datetime(2024, 1, 1, 12, 0))
    tx = Transaction("transfer", 100, "RUB",
                     from_account_id="src", to_account_id="dst",
                     commission=0, transaction_id="a",
                     priority=1, scheduled_at=datetime(2024, 1, 1, 18, 0))
    q.enqueue(tx)
    assert q.dequeue() is None
    assert len(q) == 0



@pytest.fixture
def bank():
    return Bank(now_provider=NOW)


@pytest.fixture
def converter():
    return CurrencyConverter({("USD", "RUB"): 90.0, ("RUB", "USD"): 0.011})


@pytest.fixture
def queue():
    return TransactionQueue(now_provider=NOW)


@pytest.fixture
def processor(bank, queue, converter):
    return TransactionProcessor(bank, queue, converter)


@pytest.fixture
def two_clients(bank):
    anna = Client("Анна", date(1990, 5, 15), {}, "anna_pass")
    oleg = Client("Олег", date(1985, 9, 1), {}, "oleg_pass")
    bank.add_client(anna)
    bank.add_client(oleg)
    return anna, oleg


@pytest.fixture
def accounts(bank, two_clients):
    anna, oleg = two_clients
    src = bank.open_account(anna.client_id, "basic", balance=1000, currency="RUB")
    dst = bank.open_account(oleg.client_id, "basic", balance=0, currency="RUB")
    return src, dst



def test_transfer_same_currency_success(processor, queue, accounts):
   
    src, dst = accounts

    tx = Transaction(
        "transfer", 100, "RUB",
        from_account_id=src.account_id,
        to_account_id=dst.account_id,
        commission=5,
        transaction_id="t1",
        now_provider=NOW,
    )
    queue.enqueue(tx)

    result = processor.process_one()


    assert result is True
    assert tx.status == "completed"
    assert tx.failure_reason is None
    assert tx.failure_code is None
    assert tx.processed_at is not None
    assert src.balance == pytest.approx(895.0)   
    assert dst.balance == pytest.approx(100.0)   
    assert tx not in queue.failed          



def test_transfer_insufficient_funds_no_balance_change(processor, queue, bank, two_clients):
   
    anna, oleg = two_clients
    src = bank.open_account(anna.client_id, "basic", balance=50, currency="RUB")
    dst = bank.open_account(oleg.client_id, "basic", balance=0, currency="RUB")

    tx = Transaction(
        "transfer", 100, "RUB",
        from_account_id=src.account_id,
        to_account_id=dst.account_id,
        commission=0,
        transaction_id="t1",
        now_provider=NOW,
        
    )
    queue.enqueue(tx)

    result = processor.process_one()

    # Провал
    assert result is False
    assert tx.status == "failed"
    assert tx.failure_code == "insufficient_funds"
    assert tx.failure_reason  
    assert tx.attempts == 1   

    
    assert src.balance == 50
    assert dst.balance == 0
    assert tx in queue.failed


def test_transfer_to_frozen_destination_fails(processor, queue, accounts):
    """Проверяет, что _get_active_account вызывается и для ПОЛУЧАТЕЛЯ тоже."""
    src, dst = accounts
    dst.freeze()
    
    processor.RETRYABLE_ERRORS = ()

    tx = Transaction(
        "transfer", 100, "RUB",
        from_account_id=src.account_id,
        to_account_id=dst.account_id,
        commission=0,
        transaction_id="t1",
        now_provider=NOW,
    )
    queue.enqueue(tx)

    result = processor.process_one()

    assert result is False
    assert tx.status == "failed"
    assert tx.failure_code == "account_frozen"
    
    assert src.balance == 1000
    assert dst.balance == 0



def test_retry_exhausted_moves_to_dead_letter(processor, queue, accounts):
    """AccountFrozenError retryable: 3 попытки → failed → dead-letter."""
    src, dst = accounts
    src.freeze()
    assert AccountFrozenError in processor.RETRYABLE_ERRORS

    tx2 = Transaction(
        "transfer", 100, "RUB",
        from_account_id=src.account_id,
        to_account_id=dst.account_id,
        commission=0,
        transaction_id="t2",
        max_attempts=3,
        now_provider=NOW,
    )
    queue.enqueue(tx2)

    
    for _ in range(3):
        processor.process_one()

    assert tx2.status == "failed"
    assert tx2.attempts == 3
    assert tx2.failure_code == "account_frozen"
    assert tx2 in queue.failed
    assert len(queue.failed) == 1
    
    assert src.balance == 1000



def test_transfer_different_currency_converts(processor, queue, bank, two_clients):
    """USD→RUB: комиссия в валюте источника, конвертируется ТОЛЬКО amount."""
    anna, oleg = two_clients
    src = bank.open_account(anna.client_id, "basic", balance=1000, currency="USD")
    dst = bank.open_account(oleg.client_id, "basic", balance=0, currency="RUB")

    tx = Transaction(
        "transfer", 100, "USD",
        from_account_id=src.account_id,
        to_account_id=dst.account_id,
        commission=5,          # 5 USD — в валюте источника
        transaction_id="t1",
        now_provider=NOW,
    )
    queue.enqueue(tx)

    result = processor.process_one()

    assert result is True
    assert tx.status == "completed"
    
    assert src.balance == pytest.approx(895.0)
   
    assert dst.balance == pytest.approx(9000.0)

def q():
    return TransactionQueue(now_provider=NOW)

@pytest.fixture
def make_tx():
    counter = [0]
    def _make(priority=5, tx_id=None, amount=100.0, tx_type="transfer", **kwargs):
        counter[0] += 1
        params = {
            "from_account_id": "src",
            "to_account_id": "dst",
            "commission": 0,
            "transaction_id": tx_id or f"tx{counter[0]}",
            "priority": priority,
            "now_provider": NOW,
        }
        if tx_type == "deposit":
            params.pop("from_account_id")
        elif tx_type == "withdraw":
            params.pop("to_account_id")
        params.update(kwargs)
        return Transaction(tx_type, amount, "RUB", **params)
    return _make

def test_entry_creates_with_uuid_and_timestamp():
    e = AuditEntry(
        level=AuditLevel.INFO,
        event_type="test_event",
        message="test message",
        now_provider=NOW,
    )
    assert e.id
    assert e.timestamp == datetime(2024, 1, 1, 12, 0)
    assert e.metadata == {}


def test_entry_rejects_string_level():
    with pytest.raises(InvalidOperationError):
        AuditEntry(level="INFO", event_type="x", message="m", now_provider=NOW)


def test_entry_rejects_empty_message():
    with pytest.raises(InvalidOperationError):
        AuditEntry(level=AuditLevel.INFO, event_type="x", message="", now_provider=NOW)


def test_entry_rejects_empty_event_type():
    with pytest.raises(InvalidOperationError):
        AuditEntry(level=AuditLevel.INFO, event_type="", message="m", now_provider=NOW)


def test_entry_rejects_non_dict_metadata():
    with pytest.raises(InvalidOperationError):
        AuditEntry(level=AuditLevel.INFO, event_type="x", message="m",
                   metadata="not a dict", now_provider=NOW)



def test_entry_to_dict_serializes():
    e = AuditEntry(level=AuditLevel.WARNING, event_type="evt", message="msg",
                   client_id="c1", transaction_id="t1",
                   metadata={"k": 1}, now_provider=NOW)
    d = e.audit_entry_to_dict()
    assert d["level"] == "WARNING"
    assert d["client_id"] == "c1"
    assert d["transaction_id"] == "t1"
    assert d["timestamp"] == "2024-01-01T12:00:00"
    assert d["metadata"] == {"k": 1}


def test_entry_to_json_roundtrip():
    e = AuditEntry(level=AuditLevel.ERROR, event_type="evt", message="msg",
                   client_id="c1", metadata={"a": 1}, now_provider=NOW)
    restored = AuditEntry.from_dict(json.loads(e.audit_entry_to_json()))
    assert restored.id == e.id
    assert restored.level is AuditLevel.ERROR
    assert restored.timestamp == e.timestamp
    assert restored.metadata == e.metadata


# ---------- AuditLog: память ----------
def test_log_info_adds_entry():
    log = AuditLog(now_provider=NOW)
    log.info("test", "message", client_id="c1")
    entries = log.get_entries()
    assert len(entries) == 1
    assert entries[0].level is AuditLevel.INFO
    assert entries[0].client_id == "c1"


def test_log_returns_entry():
    log = AuditLog(now_provider=NOW)
    e = log.warning("evt", "msg")
    assert isinstance(e, AuditEntry)
    assert e.level is AuditLevel.WARNING


def test_log_all_levels():
    log = AuditLog(now_provider=NOW)
    log.info("a", "1")
    log.warning("b", "2")
    log.error("c", "3")
    log.critical("d", "4")
    assert len(log) == 4
    assert log.count_by_level() == {
        AuditLevel.INFO: 1,
        AuditLevel.WARNING: 1,
        AuditLevel.ERROR: 1,
        AuditLevel.CRITICAL: 1,
    }


def test_max_entries_evicts_oldest():
    log = AuditLog(max_entries=3, now_provider=NOW)
    for i in range(5):
        log.info("evt", f"msg{i}")
    assert len(log) == 3
    messages = [e.message for e in log.get_entries()]
    assert messages == ["msg2", "msg3", "msg4"]


def test_clear_memory():
    log = AuditLog(now_provider=NOW)
    log.info("a", "1")
    log.info("b", "2")
    log.clear_memory()
    assert len(log) == 0


# ---------- AuditLog: фильтрация ----------
def test_filter_by_level():
    log = AuditLog(now_provider=NOW)
    log.info("a", "1")
    log.warning("b", "2")
    log.warning("c", "3")

    result = log.get_entries(level=AuditLevel.WARNING)
    assert [e.event_type for e in result] == ["b", "c"]


def test_filter_by_event_type():
    log = AuditLog(now_provider=NOW)
    log.info("tx_done", "1")
    log.info("auth", "2")
    log.info("tx_done", "3")

    result = log.get_entries(event_type="tx_done")
    assert len(result) == 2
    assert all(e.event_type == "tx_done" for e in result)


def test_filter_by_client_id():
    log = AuditLog(now_provider=NOW)
    log.info("a", "1", client_id="c1")
    log.info("b", "2", client_id="c2")
    log.info("c", "3", client_id="c1")

    result = log.get_entries(client_id="c1")
    assert len(result) == 2


def test_filter_by_transaction_id():
    log = AuditLog(now_provider=NOW)
    log.info("a", "1", transaction_id="t1")
    log.info("b", "2", transaction_id="t2")

    result = log.get_entries(transaction_id="t2")
    assert len(result) == 1


def test_filter_by_since_until():
    times = iter([datetime(2024, 1, 1, 10, 0),
                  datetime(2024, 1, 1, 12, 0),
                  datetime(2024, 1, 1, 14, 0)])
    log = AuditLog(now_provider=lambda: next(times))
    log.info("a", "1")
    log.info("b", "2")
    log.info("c", "3")

    result = log.get_entries(
        since=datetime(2024, 1, 1, 11, 0),
        until=datetime(2024, 1, 1, 13, 0),
    )
    assert len(result) == 1
    assert result[0].message == "2"


def test_filter_combined():
    log = AuditLog(now_provider=NOW)
    log.warning("risk", "1", client_id="c1")
    log.warning("risk", "2", client_id="c2")
    log.info("risk", "3", client_id="c1")

    result = log.get_entries(level=AuditLevel.WARNING, client_id="c1")
    assert len(result) == 1
    assert result[0].message == "1"


def test_filter_limit_returns_last_n():
    log = AuditLog(now_provider=NOW)
    for i in range(5):
        log.info("e", f"m{i}")
    result = log.get_entries(limit=2)
    assert [e.message for e in result] == ["m3", "m4"]


def test_filter_reverse():
    log = AuditLog(now_provider=NOW)
    for i in range(3):
        log.info("e", f"m{i}")
    result = log.get_entries(limit=2, reverse=True)
    assert [e.message for e in result] == ["m2", "m1"]


def test_filter_returns_copy():
    log = AuditLog(now_provider=NOW)
    log.info("a", "1")
    result = log.get_entries()
    result.clear()
    assert len(log) == 1


# ---------- AuditLog: счётчики ----------
def test_count_by_level_includes_all_levels():
    log = AuditLog(now_provider=NOW)
    log.info("a", "1")
    log.info("b", "2")
    log.warning("c", "3")
    counts = log.count_by_level()
    assert counts[AuditLevel.INFO] == 2
    assert counts[AuditLevel.WARNING] == 1
    assert counts[AuditLevel.ERROR] == 0
    assert counts[AuditLevel.CRITICAL] == 0


def test_count_by_event_type():
    log = AuditLog(now_provider=NOW)
    log.info("tx_done", "1")
    log.info("tx_done", "2")
    log.info("auth", "3")
    counts = log.count_by_event_type()
    assert counts == {"tx_done": 2, "auth": 1}


# ---------- AuditLog: файл ----------
def test_writes_to_file(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(log_file=path, now_provider=NOW)
    log.info("evt1", "1")
    log.warning("evt2", "2")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    parsed = json.loads(lines[0])
    assert parsed["event_type"] == "evt1"


def test_no_file_when_log_file_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log = AuditLog(now_provider=NOW)
    log.info("evt", "msg")
    assert list(tmp_path.iterdir()) == []


def test_file_write_failure_does_not_raise(tmp_path, monkeypatch):
    """Если запись в файл падает — log() не должен падать."""
    path = tmp_path / "audit.jsonl"
    log = AuditLog(log_file=path, now_provider=NOW)

    def failing_open(*args, **kwargs):
        raise OSError("Disk full")

    monkeypatch.setattr("pathlib.Path.open", failing_open)
    # Не падает
    entry = log.info("evt", "msg")
    # В память запись попала
    assert len(log) == 1
    assert entry.id in [e.id for e in log.get_entries()]


def test_export_to_file(tmp_path):
    log = AuditLog(now_provider=NOW)
    for i in range(3):
        log.info("e", f"m{i}")

    export_path = tmp_path / "export.jsonl"
    log.export_to_file(export_path)

    lines = export_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3

class FakeTx:
    def __init__(self, amount=500.0, currency="RUB",
                 from_id="src", to_id="dst"):
        self.id = "tx1"
        self.amount = amount
        self.currency = currency
        self.from_account_id = from_id
        self.to_account_id = to_id


# ---------- Заглушка Bank ----------
class FakeAccount:
    def __init__(self, created_at):
        self.created_at = created_at


class FakeRiskBank:
    def __init__(self):
        self.account_owners = {"src": "c1", "dst": "c1"}
        self.accounts = {}


@pytest.fixture
def Fake_bank():
    return FakeRiskBank()


@pytest.fixture
def analyzer(bank):
    return RiskAnalyzer(bank=bank, audit_log=None, now_provider=NOW)



@pytest.mark.parametrize("hour,start,end,expected", [
    (12, 22, 6, False),   # день
    (22, 22, 6, True),    # начало
    (23, 22, 6, True),    # внутри
    (0, 22, 6, True),     # через полночь
    (5, 22, 6, True),     # внутри до конца
    (6, 22, 6, False),    # конец (исключительно)
    (12, 9, 17, True),    # обычное окно
    (17, 9, 17, False),   # конец обычного окна
    (8, 9, 17, False),    # до окна
    (12, 0, 0, False),    # пустое окно
])
def test_in_window(hour, start, end, expected):
    assert RiskAnalyzer._in_window(hour, start, end) is expected



def test_low_risk_normal_transaction(analyzer):
    tx = FakeTx(amount=500.0)
    event = analyzer.analyze_transaction(tx, client_id="c1")
    assert event.level is RiskLevel.LOW
    assert event.reasons == []
    assert event.score == 0


def test_large_amount_medium(analyzer):
    tx = FakeTx(amount=150_000)
    event = analyzer.analyze_transaction(tx, client_id="c1")
    assert event.level is RiskLevel.MEDIUM
    assert any("large amount" in r for r in event.reasons)


def test_large_amount_threshold_override(bank):
    analyzer = RiskAnalyzer(
        bank=bank, now_provider=NOW,
        thresholds={"large_amount": {"RUB": 500_000}},
    )
    tx = FakeTx(amount=200_000)   # 200k < 500k
    event = analyzer.analyze_transaction(tx, client_id="c1")
    assert not any("large amount" in r for r in event.reasons)


def test_unknown_currency_skips_large_amount(analyzer):
    tx = FakeTx(amount=1_000_000, currency="XYZ")
    event = analyzer.analyze_transaction(tx, client_id="c1")
    assert not any("large amount" in r for r in event.reasons)


# ---------- Правило 2: частые операции ----------
def test_frequent_operations_flagged(bank):
    audit = AuditLog(now_provider=NOW)
    analyzer = RiskAnalyzer(bank=bank, audit_log=audit, now_provider=NOW)

    # 5 завершённых операций за последние 10 минут
    for _ in range(5):
        audit.info("transaction_completed", "done", client_id="c1")

    tx = FakeTx()
    event = analyzer.analyze_transaction(tx, client_id="c1")
    assert any("frequent" in r for r in event.reasons)


def test_not_frequent_below_threshold(bank):
    audit = AuditLog(now_provider=NOW)
    analyzer = RiskAnalyzer(bank=bank, audit_log=audit, now_provider=NOW)

    for _ in range(4):
        audit.info("transaction_completed", "done", client_id="c1")

    tx = FakeTx()
    event = analyzer.analyze_transaction(tx, client_id="c1")
    assert not any("frequent" in r for r in event.reasons)


def test_frequency_no_audit_log(bank):
    analyzer = RiskAnalyzer(bank=bank, audit_log=None, now_provider=NOW)
    tx = FakeTx()
    event = analyzer.analyze_transaction(tx, client_id="c1")
    # Не падает, правило пропущено
    assert not any("frequent" in r for r in event.reasons)


def test_frequency_only_completed_counted(bank):
    """transaction_failed / transaction_retry НЕ считаются в частоту."""
    audit = AuditLog(now_provider=NOW)
    analyzer = RiskAnalyzer(bank=bank, audit_log=audit, now_provider=NOW)

    for _ in range(10):
        audit.error("transaction_failed", "fail", client_id="c1")

    tx = FakeTx()
    event = analyzer.analyze_transaction(tx, client_id="c1")
    assert not any("frequent" in r for r in event.reasons)



def test_new_account_flagged(bank):
    # Счёт открыт 5 дней назад — меньше 30
    bank.accounts["dst"] = FakeAccount(
        created_at=datetime(2023, 12, 27, 12, 0)
    )
    analyzer = RiskAnalyzer(bank=bank, now_provider=NOW)
    tx = FakeTx(to_id="dst")
    event = analyzer.analyze_transaction(tx, client_id="c1")
    assert any("new account" in r for r in event.reasons)


def test_old_account_not_flagged(bank):
    bank.accounts["dst"] = FakeAccount(
        created_at=datetime(2023, 1, 1, 12, 0)
    )
    analyzer = RiskAnalyzer(bank=bank, now_provider=NOW)
    tx = FakeTx(to_id="dst")
    event = analyzer.analyze_transaction(tx, client_id="c1")
    assert not any("new account" in r for r in event.reasons)


def test_missing_to_account_skips_rule(bank):
    """withdraw: to_account_id=None → правило пропущено."""
    analyzer = RiskAnalyzer(bank=bank, now_provider=NOW)
    tx = FakeTx(to_id=None)
    event = analyzer.analyze_transaction(tx, client_id="c1")
    assert not any("new account" in r for r in event.reasons)


# ---------- Правило 4: ночь ----------
def test_night_operation_flagged(bank):
    night_now = lambda: datetime(2024, 1, 1, 3, 0)
    analyzer = RiskAnalyzer(bank=bank, now_provider=night_now)
    tx = FakeTx()
    event = analyzer.analyze_transaction(tx, client_id="c1")
    assert any("night" in r for r in event.reasons)


def test_day_operation_not_flagged(analyzer):
    tx = FakeTx()
    event = analyzer.analyze_transaction(tx, client_id="c1")
    assert not any("night" in r for r in event.reasons)


def test_night_window_boundary_start(bank):
    """22:00 — включительно."""
    now = lambda: datetime(2024, 1, 1, 22, 0)
    analyzer = RiskAnalyzer(bank=bank, now_provider=now)
    event = analyzer.analyze_transaction(FakeTx(), client_id="c1")
    assert any("night" in r for r in event.reasons)


def test_night_window_boundary_end(bank):
    """06:00 — исключительно (не ночь)."""
    now = lambda: datetime(2024, 1, 1, 6, 0)
    analyzer = RiskAnalyzer(bank=bank, now_provider=now)
    event = analyzer.analyze_transaction(FakeTx(), client_id="c1")
    assert not any("night" in r for r in event.reasons)


def test_night_window_override(bank):
    analyzer = RiskAnalyzer(
        bank=bank, now_provider=NOW,
        thresholds={"night_hours": (0, 24)},
    )
    event = analyzer.analyze_transaction(FakeTx(), client_id="c1")
    assert any("night" in r for r in event.reasons)



@pytest.mark.parametrize("count,expected", [
    (0, RiskLevel.LOW),
    (1, RiskLevel.MEDIUM),
    (2, RiskLevel.MEDIUM),
    (3, RiskLevel.HIGH),
    (4, RiskLevel.HIGH),
])
def test_level_aggregation(count, expected):
    assert RiskAnalyzer._level_for(count) is expected


def test_three_rules_high(bank):
    # крупная + ночь + новый счёт
    bank.accounts["dst"] = FakeAccount(
        created_at=datetime(2023, 12, 31, 12, 0)
    )
    night_now = lambda: datetime(2024, 1, 1, 3, 0)
    analyzer = RiskAnalyzer(bank=bank, now_provider=night_now)
    tx = FakeTx(amount=500_000)
    event = analyzer.analyze_transaction(tx, client_id="c1")
    assert event.level is RiskLevel.HIGH
    assert event.score >= 3
    assert event.should_block() is True



def test_should_block_only_high():
    def make(level):
        return RiskEvent("t1", "c1", [], level, now_provider=NOW)
    assert make(RiskLevel.LOW).should_block() is False
    assert make(RiskLevel.MEDIUM).should_block() is False
    assert make(RiskLevel.HIGH).should_block() is True


def test_risk_event_to_dict():
    e = RiskEvent("t1", "c1", ["reason1"], RiskLevel.MEDIUM, now_provider=NOW)
    d = e.risk_event_to_dict()
    assert d["transaction_id"] == "t1"
    assert d["level"] == "MEDIUM"
    assert d["score"] == 1
    assert d["reasons"] == ["reason1"]


def test_risk_event_reasons_copied():
    reasons = ["r1"]
    e = RiskEvent("t1", "c1", reasons, RiskLevel.MEDIUM, now_provider=NOW)
    reasons.append("r2")
    assert e.reasons == ["r1"]
    assert e.score == 1


def test_invalid_frequency_window(bank):
    with pytest.raises(InvalidOperationError):
        RiskAnalyzer(bank=bank, now_provider=NOW,
                     thresholds={"frequency_window_minutes": 0})


def test_invalid_frequency_max(bank):
    with pytest.raises(InvalidOperationError):
        RiskAnalyzer(bank=bank, now_provider=NOW,
                     thresholds={"frequency_max_operations": 0})


def test_invalid_night_hours(bank):
    with pytest.raises(InvalidOperationError):
        RiskAnalyzer(bank=bank, now_provider=NOW,
                     thresholds={"night_hours": (22,)})  


 
class FakeClient:
    def __init__(self, cid, name):
        self.client_id = cid
        self.full_name = name


class FakeBank:
    def __init__(self):
        self.clients = {
            "c1": FakeClient("c1", "Анна"),
            "c2": FakeClient("c2", "Олег"),
        }


@pytest.fixture
def audit():
    return AuditLog(now_provider=NOW)


@pytest.fixture
def reporter(audit):
    return AuditReporter(audit_log=audit, bank=FakeBank())


# ---------- report_suspicious_operations ----------
def test_suspicious_empty(audit, reporter):
    result = reporter.report_suspicious_operations()
    assert result["total_alerts"] == 0
    assert result["total_blocked"] == 0
    assert result["by_client"] == {}


def test_suspicious_groups_by_client(audit, reporter):
    audit.warning("risk_alert", "m", client_id="c1", risk_level="medium", reasons=["r1"])
    audit.warning("risk_alert", "m", client_id="c1", risk_level="medium", reasons=["r2"])
    audit.critical("risk_blocked", "m", client_id="c2", risk_level="high", reasons=["r3"])

    result = reporter.report_suspicious_operations()
    assert result["total_alerts"] == 2
    assert result["total_blocked"] == 1
    assert len(result["by_client"]["c1"]["alerts"]) == 2
    assert len(result["by_client"]["c2"]["blocked"]) == 1


def test_suspicious_includes_client_name(audit, reporter):
    audit.warning("risk_alert", "m", client_id="c1", reasons=["r"])
    result = reporter.report_suspicious_operations()
    assert result["by_client"]["c1"]["client_name"] == "Анна"


def test_suspicious_works_without_bank(audit):
    reporter = AuditReporter(audit_log=audit, bank=None)
    audit.warning("risk_alert", "m", client_id="c1", reasons=["r"])
    result = reporter.report_suspicious_operations()
    assert result["by_client"]["c1"]["client_name"] is None


def test_suspicious_respects_since(audit, reporter):
    times = iter([datetime(2024, 1, 1, 10, 0),
                  datetime(2024, 1, 1, 14, 0)])
    audit._now = lambda: next(times)
    audit.warning("risk_alert", "old", client_id="c1", reasons=["a"])
    audit.warning("risk_alert", "new", client_id="c1", reasons=["b"])

    result = reporter.report_suspicious_operations(
        since=datetime(2024, 1, 1, 12, 0)
    )
    assert result["total_alerts"] == 1


# ---------- report_client_risk_profile ----------
def test_profile_unknown_client(reporter):
    with pytest.raises(ClientNotFoundError):
        reporter.report_client_risk_profile("unknown")


def test_profile_distribution(audit, reporter):
    audit.warning("risk_alert", "m", client_id="c1", risk_level="medium", reasons=["r1"])
    audit.warning("risk_alert", "m", client_id="c1", risk_level="medium", reasons=["r2"])
    audit.critical("risk_blocked", "m", client_id="c1", risk_level="high", reasons=["r3"])

    result = reporter.report_client_risk_profile("c1")
    assert result["risk_distribution"]["medium"] == 2
    assert result["risk_distribution"]["high"] == 1
    assert result["blocked_count"] == 1


def test_profile_top_reasons(audit, reporter):
    audit.warning("risk_alert", "m", client_id="c1", reasons=["large", "frequent"])
    audit.warning("risk_alert", "m", client_id="c1", reasons=["large"])

    result = reporter.report_client_risk_profile("c1")
    reasons = {r["reason"]: r["count"] for r in result["top_reasons"]}
    assert reasons["large"] == 2
    assert reasons["frequent"] == 1


def test_profile_empty_for_new_client(audit, reporter):
    result = reporter.report_client_risk_profile("c1")
    assert result["risk_distribution"] == {"low": 0, "medium": 0, "high": 0}
    assert result["blocked_count"] == 0
    assert result["top_reasons"] == []
    assert result["last_activity"] is None


# ---------- report_error_statistics ----------
def test_errors_empty(audit, reporter):
    result = reporter.report_error_statistics()
    assert result["total_errors"] == 0
    assert result["by_code"] == {}


def test_errors_by_code(audit, reporter):
    audit.error("transaction_failed", "m", failure_code="insufficient_funds")
    audit.error("transaction_failed", "m", failure_code="insufficient_funds")
    audit.error("transaction_failed", "m", failure_code="account_frozen")

    result = reporter.report_error_statistics()
    assert result["total_errors"] == 3
    assert result["by_code"]["insufficient_funds"] == 2
    assert result["by_code"]["account_frozen"] == 1


def test_errors_only_error_level(audit, reporter):
    """WARNING/INFO/CRITICAL не считаются в статистику ошибок."""
    audit.info("transaction_failed", "m", failure_code="x")
    audit.warning("transaction_failed", "m", failure_code="y")
    audit.error("transaction_failed", "m", failure_code="z")

    result = reporter.report_error_statistics()
    assert result["total_errors"] == 1
    assert result["by_code"] == {"z": 1}


def test_errors_unknown_code_fallback(audit, reporter):
    """Запись без failure_code → 'unknown'."""
    audit.error("transaction_failed", "m")   # без failure_code
    result = reporter.report_error_statistics()
    assert result["by_code"] == {"unknown": 1}


def test_errors_by_event_type(audit, reporter):
    audit.error("transaction_failed", "m", failure_code="a")
    audit.error("auth_failed", "m", failure_code="b")
    result = reporter.report_error_statistics()
    assert result["by_event_type"] == {
        "transaction_failed": 1,
        "auth_failed": 1,
    }