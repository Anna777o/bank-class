from abc import ABC, abstractmethod
import uuid
from utils import (
    AccountFrozenError, AccountClosedError, 
    InvalidOperationError, InsufficientFundsError, 
    validate_amount
)

class AbstractAccount(ABC):
    """Abstract base class"""
    def __init__(self, owner: str, account_id: str=None, balance: float = 0.0):
        self.account_id = str(uuid.uuid4()) if account_id is None else account_id
        self.balance = balance
        self.owner = owner
        self.status = "active"
    @abstractmethod
    def deposit(self, amount: float) -> None:
        """Deposit a specified amount into the account."""
        pass

    @abstractmethod
    def withdraw(self, amount: float) -> None:
        pass

    @abstractmethod
    def get_account_info(self) -> str:
        """Return account information."""
        pass

class BankAccount(AbstractAccount):
    """Main class for bank account"""
    VALID_CURRENCIES = ["RUB", "USD", "EUR", "KZT", "CNY"]
    def __init__(self, owner: str, account_id: str=None, balance: float = 0.0, currency: str = "USD"):
        super().__init__(owner, account_id, balance)
        if currency not in self.VALID_CURRENCIES:
            raise InvalidOperationError(f"Invalid currency. Valid options are: {', '.join(self.VALID_CURRENCIES)}")
        self.currency = currency

    def check_status(self) -> None:
        """Check the account status and raise an error if it's not active."""
        if self.status == "frozen":
            raise AccountFrozenError("Account is frozen.")
        elif self.status == "closed":
            raise AccountClosedError("Account is closed.")
        
    def deposit(self, amount: float) -> None:
        """Deposit a specified amount into the account."""
        self.check_status()
        validate_amount(amount)
        self.balance += amount

    def withdraw(self, amount: float) -> None:
        """Withdraw a specified amount from the account."""
        self.check_status()
        validate_amount(amount)
        if amount > self.balance:
            raise InsufficientFundsError("Insufficient funds for this withdrawal.")
        self.balance -= amount

    def get_account_info(self) -> str:
        """Return account information."""
        return {
            "account_id": self.account_id,
            "owner": self.owner,
            "balance": self.balance,
            "currency": self.currency,
            "status": self.status
        }

    def __str__(self) -> str:
        """Return a string representation of the account."""
        masked_id = f"***{self.account_id[-4:]}" if len(self.account_id) >= 4 else self.account_id
        return (f"Тип: {self.__class__.__name__} | "
                f"Клиент: {self.owner} | "
                f"Счет: {masked_id} | "
                f"Статус: {self.status.upper()} | "
                f"Баланс: {self.balance} {self.currency}")