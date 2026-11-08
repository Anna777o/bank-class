import pytest
import sys
import os
import hashlib
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from datetime import date, datetime, timedelta
from models import BankAccount, SavingsAccount, PremiumAccount, InvestmentAccount, Client, Bank
from utils import (
    ClientNotAdultError, ClientBlockedError, AuthenticationError,
    RestrictedTimeError, AccountNotFoundError, ClientNotAdultError, AccountClosedError,
    AccountFrozenError, InvalidOperationError, InsufficientFundsError, validate_amount
)

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