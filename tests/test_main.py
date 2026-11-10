import pytest
import sys
import os
import hashlib
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from datetime import date, datetime, timedelta
from models import BankAccount, SavingsAccount, PremiumAccount, InvestmentAccount, Client, Bank, Transaction, TransactionQueue, TransactionProcessor
from utils import (
    ClientNotAdultError, ClientBlockedError, AuthenticationError,
    RestrictedTimeError, AccountNotFoundError, ClientNotAdultError, AccountClosedError,
    AccountFrozenError, InvalidOperationError, InsufficientFundsError, validate_amount
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

def test_cancel_unknown_returns_false(q):
    q = TransactionQueue(now_provider=lambda: datetime(2024, 1, 1, 12, 0))
    assert q.cancel("nonexistent") is False

def test_cancel_twice_is_idempotent(q, make_tx):
    q = TransactionQueue(now_provider=lambda: datetime(2024, 1, 1, 12, 0))
    tx = Transaction("transfer", 100, "RUB", id = "x",
                     from_account_id="src", to_account_id="dst",
                     commission=0, transaction_id="a",
                     priority=1, now_provider=NOW)
    q.enqueue(tx)

    assert q.cancel("x") is True       
    assert q.cancel("x") is False      
    assert tx.status == "cancelled"    


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