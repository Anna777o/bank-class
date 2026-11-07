import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from models import BankAccount
from utils import AccountFrozenError, AccountClosedError, InvalidOperationError, InsufficientFundsError

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