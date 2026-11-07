import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from models import BankAccount, SavingsAccount, PremiumAccount, InvestmentAccount
from utils import AccountFrozenError, AccountClosedError, InvalidOperationError, InsufficientFundsError
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