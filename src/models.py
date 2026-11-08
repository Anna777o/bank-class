from abc import ABC, abstractmethod
import uuid
from utils import (
    ClientNotAdultError, ClientBlockedError, AuthenticationError,
    RestrictedTimeError, AccountNotFoundError, ClientNotAdultError, AccountClosedError,
    AccountFrozenError, InvalidOperationError, InsufficientFundsError, validate_amount,
)
import hashlib
from datetime import date, datetime

#day1
class AbstractAccount(ABC):
    """Abstract base class"""
    def __init__(self, owner: str, account_id: str=None, balance: float = 0.0):
        self.account_id = str(uuid.uuid4()) if account_id is None else account_id
        self._balance = balance
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
        self._balance += amount

    def withdraw(self, amount: float) -> None:
        """Withdraw a specified amount from the account."""
        self.check_status()
        validate_amount(amount)
        if amount > self.balance:
            raise InsufficientFundsError("Insufficient funds for this withdrawal.")
        self._balance -= amount

    def get_account_info(self) -> str:
        """Return account information."""
        return {
            "account_id": self.account_id,
            "owner": self.owner,
            "balance": self.balance,
            "currency": self.currency,
            "status": self.status
        }
    @property
    def balance(self) -> float:
        """Публичный доступ к балансу (read-only)."""
        return self._balance

    def freeze(self) -> None:
        if self.status == "closed":
            raise InvalidOperationError("Нельзя заморозить закрытый счет")
        self.status = "frozen"

    def unfreeze(self) -> None:
        if self.status == "closed":
            raise InvalidOperationError("Нельзя разморозить закрытый счет")
        self.status = "active"

    def close(self) -> None:
        if self._balance != 0:
            raise InvalidOperationError(
                f"Нельзя закрыть счет с ненулевым балансом: "
                f"{self._balance} {self.currency}. Сначала снимите средства."
            )
        self.status = "closed"

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
        self._balance += self._balance * self.interest_rate
        print(f"[{self.account_id}] Percents: {self._balance * self.interest_rate:.2f} {self.currency}. Новый баланс: {self._balance:.2f}")

    def withdraw(self, amount: float) -> None:
        self.check_status()
        validate_amount(amount)
        if self.balance - amount < self.min_balance:
            raise InvalidOperationError(f"Impossible to withdraw. Balance will fall below minimum balance ({self.min_balance} {self.currency}).")
        self._balance -= amount

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
        self._balance -= total
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
        self._balance -= amount
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

#day3
class Client():
    """Class for bank clients"""
    MIN_AGE = 18
    def __init__(self, full_name: str, birth_date: date, contacts: dict, password: str):
        self.client_id = str(uuid.uuid4())[:8]
        self.full_name = full_name
        self.birth_date = birth_date
        self.contacts = contacts
        self.status = "active"             
        self.account_ids: list[str] = []
        self.failed_attempts = 0
        self.suspicious_activity = False
        self.activity_log: list[str] = []
        self._password_hash = self._hash_password(password)

        self.check_age()

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def check_age(self) -> None:
        today_date = date.today()
        age = today_date.year - self.birth_date.year - (
            (today_date.month, today_date.day) < (self.birth_date.month, self.birth_date.day)
        )
        if age < self.MIN_AGE:
            raise ClientNotAdultError(
                f"Client should be not younger than {self.MIN_AGE}. Current age: {age}"
            )

    def verify_password(self, password: str) -> bool:
        return self._hash_password(password) == self._password_hash

    def link_account(self, account_id: str) -> None:
        """Adding bank account id to a client"""
        if account_id not in self.account_ids:
            self.account_ids.append(account_id)

    def unlink_account(self, account_id: str) -> None:
        """Excluding bank account id from a client"""
        if account_id in self.account_ids:
            self.account_ids.remove(account_id)

    def mark_suspicious(self, reason: str) -> None:
        """Marking client account suspicious"""
        self.suspicious_activity = True
        self.log_activity(f"SUSPICIOUS: {reason}")
    
    def log_activity(self, message: str) -> None:
        self.activity_log.append(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}")

    def get_info(self) -> dict:
        return {
            "client_id": self.client_id,
            "full_name": self.full_name,
            "status": self.status,
            "accounts": list(self.account_ids),
            "contacts": dict(self.contacts),
            "suspicious": self.suspicious_activity,
        }
    
    def __str__(self) -> str:
        """Return string represintation of client account"""
        return (
            f"Client {self.client_id} | {self.full_name} | "
            f"Status: {self.status.upper()} | Accounts: {len(self.account_ids)} | "
            f"Suspicious: {'YES' if self.suspicious_activity else 'no'}"
        )
class Bank():
    """Class for bank"""
    RESTRICTED_HOURS = (0, 5)        # 00:00 – 05:00
    MAX_FAILED_ATTEMPTS = 3

    ACCOUNT_TYPES = {
        "basic": BankAccount,
        "savings": SavingsAccount,
        "premium": PremiumAccount,
        "investment": InvestmentAccount,
    }

    def __init__(self, now_provider=None):
        self.clients: dict[str, Client] = {}
        self.accounts: dict[str, BankAccount] = {}
        
        self._now = now_provider or datetime.now

    
    def _is_restricted_time(self) -> bool:
        hour = self._now().hour
        return self.RESTRICTED_HOURS[0] <= hour < self.RESTRICTED_HOURS[1]

    def _check_time(self) -> None:
        if self._is_restricted_time():
            raise RestrictedTimeError(
                f"Operations are prohibited from {self.RESTRICTED_HOURS[0]:02d}:00 "
                f"to {self.RESTRICTED_HOURS[1]:02d}:00"
            )

    def _get_client(self, client_id: str) -> Client:
        client = self.clients.get(client_id)
        if not client:
            raise ClientNotFoundError(f"Client {client_id} not found")
        return client

    def _get_account(self, account_id: str) -> BankAccount:
        account = self.accounts.get(account_id)
        if not account:
            raise AccountNotFoundError(f"Account {account_id} not found")
        return account

    def _ensure_owner(self, client: Client, account_id: str) -> None:
        if account_id not in client.account_ids:
            client.mark_suspicious(f"Attempt of operation with other account {account_id}")
            raise InvalidOperationError("Account does not belong to this client")
    
    def add_client(self, client: Client) -> str:
        self.clients[client.client_id] = client
        return client.client_id
    
    def authenticate_client(self, client_id: str, password: str) -> bool:
        client = self._get_client(client_id)

        if client.status == "blocked":
            raise ClientBlockedError(f"Client {client_id} is blocked")

        if client.verify_password(password):
            client.failed_attempts = 0
            client.log_activity("Successful")
            return True

    
        client.failed_attempts += 1
        client.log_activity(
            f"Authenfication attempt failed ({client.failed_attempts}/{self.MAX_FAILED_ATTEMPTS})"
        )

        if client.failed_attempts >= self.MAX_FAILED_ATTEMPTS:
            client.status = "blocked"
            client.mark_suspicious(
                f"The number of login restrictions has been exceeded ({self.MAX_FAILED_ATTEMPTS})"
            )
            raise ClientBlockedError(
                f"Client {client_id} was blockef after "
                f"{self.MAX_FAILED_ATTEMPTS} failed attempts"
            )

        raise AuthenticationError(
            f"Wrong password. Attempts left: "
            f"{self.MAX_FAILED_ATTEMPTS - client.failed_attempts}"
        )

    def open_account(self, client_id: str, account_type: str = "basic", **kwargs) -> BankAccount:
        self._check_time()
        client = self._get_client(client_id)

        if client.status == "blocked":
            raise ClientBlockedError(f"Client {client_id} is blocked")

        if account_type not in self.ACCOUNT_TYPES:
            raise InvalidOperationError(
                f"Account type is not available: {account_type}. "
                f"Available: {', '.join(self.ACCOUNT_TYPES)}"
            )

        account_cls = self.ACCOUNT_TYPES[account_type]
        account = account_cls(owner=client.full_name, **kwargs)

        self.accounts[account.account_id] = account
        client.link_account(account.account_id)
        client.log_activity(f"Open account {account.account_id} ({account_type})")
        return account
    
    def close_account(self, account_id: str) -> None:
        self._check_time()
        self._get_account(account_id).close()

    def freeze_account(self, account_id: str) -> None:
        self._check_time()
        self._get_account(account_id).freeze()

    def unfreeze_account(self, account_id: str) -> None:
        self._check_time()
        self._get_account(account_id).unfreeze()

    def deposit(self, client_id: str, password: str, account_id: str, amount: float) -> None:
        self._check_time()
        self.authenticate_client(client_id, password)
        client = self._get_client(client_id)
        self._ensure_owner(client, account_id)

        self._get_account(account_id).deposit(amount)
        client.log_activity(f"Deposit {account_id} on {amount}")

    def withdraw(self, client_id: str, password: str, account_id: str, amount: float) -> None:
        self._check_time()
        self.authenticate_client(client_id, password)
        client = self._get_client(client_id)
        self._ensure_owner(client, account_id)

        self._get_account(account_id).withdraw(amount)
        client.log_activity(f"Withdraw from {account_id}: {amount}")

    def search_accounts(self, query: str = "", status: str = None) -> list[BankAccount]:
        q = query.lower()
        result = []
        for acc in self.accounts.values():
            if q and q not in acc.account_id.lower() and q not in acc.owner.lower():
                continue
            if status and acc.status != status:
                continue
            result.append(acc)
        return result

    def get_total_balance(self, client_id: str = None) -> float:
        
        if client_id:
            client = self._get_client(client_id)
            return sum(
                self.accounts[aid].balance
                for aid in client.account_ids
                if aid in self.accounts
            )
        return sum(acc.balance for acc in self.accounts.values())

    def get_clients_ranking(self) -> list[tuple[Client, float]]:
        
        ranking = [
            (client, self.get_total_balance(client.client_id))
            for client in self.clients.values()
        ]
        ranking.sort(key=lambda x: x[1], reverse=True)
        return ranking