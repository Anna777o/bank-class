from abc import ABC, abstractmethod
import uuid
from utils import (
    AccountFrozenError, AccountClosedError, 
    InvalidOperationError, InsufficientFundsError, 
    validate_amount
)
#day1
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

#day2
class SavingsAccount(BankAccount):
    """Savings account with interest."""
    def __init__(self, owner: str, account_id: str=None, balance: float = 0.0, currency: str = "USD", interest_rate: float = 0.01, min_balance: float = 100.0):
        super().__init__(owner, account_id, balance, currency)
        self.interest_rate = interest_rate
        self.min_balance = min_balance

    def apply_monthly_interest(self) -> None:
        """Apply monthly interest to the account balance."""
        self.check_status()
        self.balance += self.balance * self.interest_rate
        print(f"[{self.account_id}] Percents: {self.balance * self.interest_rate:.2f} {self.currency}. Новый баланс: {self.balance:.2f}")

    def withdraw(self, amount: float) -> None:
        self.check_status()
        validate_amount(amount)
        if self.balance - amount < self.min_balance:
            raise InvalidOperationError(f"Impossible to withdraw. Balance will fall below minimum balance ({self.min_balance} {self.currency}).")
        self.balance -= amount

    def get_account_info(self) -> dict:
        """Return account information."""
        info = super().get_account_info()
        info.update({"min_balance": self.min_balance, "interest_rate": self.monthly_interest_rate})
        return info

    def __str__(self) -> str:
        """Return a string representation of the savings account."""
        base_str = super().__str__()
        return f"{base_str} | Min Balance: {self.min_balance} {self.currency} | Interest Rate: {self.interest_rate * 100:.2f}%"

class PremiumAccount(BankAccount):
    """Premium account with higher interest and benefits."""
    def __init__(self, owner: str, account_id: str=None, balance: float = 0.0, currency: str = "USD", overdraft_limit: float = 1000.0, commission: float = 50.0):
        super().__init__(owner, account_id, balance, currency)
        self.overdraft_limit = overdraft_limit
        self.commission = commission

    def withdraw(self, amount: float) -> None:
        self.check_status()
        validate_amount(amount)
        total = amount + self.commission
        if self.balance - total < -self.overdraft_limit:
            raise InsufficientFundsError(f"Impossible to withdraw. Overdraft limit exceeded ({self.overdraft_limit} {self.currency}).")  
        self.balance -= total
        print(f"[{self.account_id}] Commission: {self.commission} {self.currency}. new balance: {self.balance:.2f}")


    def get_account_info(self) -> dict:
        """Return account information."""
        info = super().get_account_info()
        info.update({"commission": self.commission, "overdraft_limit": self.overdraft_limit})
        return info

    def __str__(self) -> str:
        """Return a string representation of the premium account."""
        base_str = super().__str__()
        return f"{base_str} | Overdraft Limit: {self.overdraft_limit} {self.currency} | Commission: {self.commission} {self.currency}"

class InvestmentAccount(BankAccount):
    VALID_ASSETS = ["stocks", "bonds", "etf"]
    """Investment account for managing investments."""
    def __init__(self, owner: str, account_id: str=None, balance: float = 0.0, currency: str = "USD"):
        super().__init__(owner, account_id, balance, currency)
        self.portfolio = {asset: 0.0 for asset in self.VALID_ASSETS}

    def invest(self, option: str, amount: float) -> None:
        self.check_status()
        validate_amount(amount)
        if option not in self.VALID_ASSETS:
            raise InvalidOperationError(f"Invalid investment option: {option}")
        if self.balance < amount:
            raise InsufficientFundsError("Insufficient funds for investment.")
        self.balance -= amount
        self.portfolio[option] += amount
        print(f"[{self.account_id}] Invested {amount} {self.currency} in {option}. New balance: {self.balance:.2f}")

    def project_yearly_growth(self,growth_rates) -> dict:
        yearly_total = 0.0
        for asset, amount in self.portfolio.items():
            rate = growth_rates.get(asset, 0.0)
            yearly_total += amount * (1 + rate)
        return yearly_total

    def get_account_info(self) -> dict:
        """Return account information."""
        info = super().get_account_info()
        info.update({"portfolio": self.portfolio})
        return info

    def __str__(self) -> str:
        """Return a string representation of the investment account."""
        base_str = super().__str__()
        total_invested = sum(self.portfolio.values())
        return f"{base_str} | Invested: {total_invested} {self.currency}"