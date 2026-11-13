from abc import ABC, abstractmethod
import uuid
from pathlib import Path
import logging
from utils import (
    ClientNotAdultError, ClientBlockedError, AuthenticationError,
    RestrictedTimeError, AccountNotFoundError, ClientNotAdultError, AccountClosedError, SuspiciousTransactionError,
    AccountFrozenError, InvalidOperationError, InsufficientFundsError, validate_amount, ClientNotFoundError, InsufficientFundsError
)
from enum import Enum
import hashlib
from datetime import date, datetime,timedelta
from collections import deque
import heapq
from collections import defaultdict, Counter
from typing import TYPE_CHECKING, Callable
import json
if TYPE_CHECKING:
    from currency_converter import CurrencyConverter
logger = logging.getLogger("audit")
#day1
class AbstractAccount(ABC):
    """Abstract base class"""
    def __init__(self, owner: str, account_id: str=None, balance: float = 0.0, now_provider=None):
        self.account_id = str(uuid.uuid4()) if account_id is None else account_id
        self._balance = balance
        self.owner = owner
        self.status = "active"
        self._now = now_provider or datetime.now     
        self.created_at = self._now()  
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
    def __init__(self, owner: str, account_id: str=None, balance: float = 0.0, currency: str = "USD", created_at: datetime = None,
                 now_provider: datetime = None):
        super().__init__(owner, account_id, balance, now_provider=now_provider)
        if currency not in self.VALID_CURRENCIES:
            raise InvalidOperationError(f"Invalid currency. Valid options are: {', '.join(self.VALID_CURRENCIES)}")
        self.currency = currency
        self.created_at = self._now()

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
    def can_send(self, amount: float) -> tuple[bool, str]:
        if self._balance <= 0:
            return (False, "Balance is lower than 0, unable to have a transaction")
        if self._balance < amount:
            return (False, "Balance is lower than amount, unable to have a transaction")
        return(True, "")

#day2
class SavingsAccount(BankAccount):
    """Savings account with interest."""
    def __init__(self, owner: str, account_id: str=None, balance: float = 0.0, currency: str = "USD", interest_rate: float = 0.01, min_balance: float = 100.0, now_provider = None):
        super().__init__(owner, account_id, balance, currency,now_provider=now_provider)
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
    def __init__(self, owner: str, account_id: str=None, balance: float = 0.0, currency: str = "USD", overdraft_limit: float = 1000.0, commission: float = 50.0, now_provider=None):
        super().__init__(owner, account_id, balance, currency, now_provider,)
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
    
    def can_send(self, amount: float) -> tuple[bool, str]:
        available = self._balance + self.overdraft_limit
        if amount > available:
            return False, (
                f"Exedded overdraft limit: needed {amount:.2f}, "
                f"available {available:.2f} {self.currency}"
            )
        return True, ""
    def __str__(self) -> str:
        """Return a string representation of the premium account."""
        base_str = super().__str__()
        return f"{base_str} | Overdraft Limit: {self.overdraft_limit} {self.currency} | Commission: {self.commission} {self.currency}"

class InvestmentAccount(BankAccount):
    VALID_ASSETS = ["stocks", "bonds", "etf"]
    """Investment account for managing investments."""
    def __init__(self, owner: str, account_id: str=None, balance: float = 0.0, currency: str = "USD", now_provider=None):
        super().__init__(owner, account_id, balance, currency, now_provider)
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
    RESTRICTED_HOURS = (0, 5)        
    MAX_FAILED_ATTEMPTS = 3

    ACCOUNT_TYPES = {
        "basic": BankAccount,
        "savings": SavingsAccount,
        "premium": PremiumAccount,
        "investment": InvestmentAccount,
    }

    def __init__(
        self,
        now_provider=None,
        audit_log: AuditLog | None = None,
        risk_analyzer: RiskAnalyzer | None = None,
        report_path: str | None = None,
    ):
        self._now = now_provider or datetime.now
        self.clients: dict[str, Client] = {}
        self.accounts: dict[str, BankAccount] = {}
        self.account_owners: dict[str, str] = {}

        self.audit_log = (
            audit_log if audit_log is not None
            else AuditLog(now_provider=self._now)
        )

        if risk_analyzer is None:
            self.risk_analyzer = RiskAnalyzer(
                bank=self,
                audit_log=self.audit_log,
                now_provider=self._now,
            )
        else:
            self.risk_analyzer = risk_analyzer
            if self.risk_analyzer.bank is None:
                self.risk_analyzer.bank = self
            if self.risk_analyzer.audit_log is None:
                self.risk_analyzer.audit_log = self.audit_log

        self.report_path = report_path
        self.reporter = AuditReporter(
            audit_log=self.audit_log,
            risk_analyzer=self.risk_analyzer,
            bank=self,
        )

    def analyze_transaction_risk(self, tx) -> RiskEvent:
        """Анализ риска + аудит + блокировка при HIGH.

        Вызывается из TransactionProcessor перед _dispatch.
        Raises: SuspiciousTransactionError при HIGH.
        """
        # Фикс 3: client_id берём из индекса account_owners
        client_id = (
            self.account_owners.get(tx.from_account_id)
            or self.account_owners.get(tx.to_account_id)
        )

        event = self.risk_analyzer.analyze_transaction(tx, client_id=client_id)

        # Фикс 4: risk_level и reasons идут в **metadata плоско
        if event.level is RiskLevel.MEDIUM:
            self.audit_log.warning(
                "risk_alert",
                f"Medium risk: {event.reasons}",
                transaction_id=tx.id,
                client_id=client_id,
                risk_level="medium",
                reasons=event.reasons,
            )

        if event.level is RiskLevel.HIGH:
            self.audit_log.critical(
                "risk_blocked",
                f"High risk blocked: {event.reasons}",
                transaction_id=tx.id,
                client_id=client_id,
                risk_level="high",
                reasons=event.reasons,
            )
            raise SuspiciousTransactionError(f"Blocked: {event.reasons}")

        return event

    # ---------- Ограничение по времени ----------
    def _is_restricted_time(self) -> bool:
        hour = self._now().hour
        start, end = self.RESTRICTED_HOURS
        return start <= hour < end

    def _check_time(self) -> None:
        if self._is_restricted_time():
            start, end = self.RESTRICTED_HOURS
            raise RestrictedTimeError(
                f"Operations are prohibited from {start:02d}:00 to {end:02d}:00"
            )

    # ---------- Внутренние ----------
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
            client.mark_suspicious(f"Attempt to operate foreign account {account_id}")
            raise InvalidOperationError("Account does not belong to this client")

    # ---------- Клиенты ----------
    def add_client(self, client: Client) -> str:
        self.clients[client.client_id] = client
        return client.client_id

    def authenticate_client(self, client_id: str, password: str) -> bool:
        client = self._get_client(client_id)

        if client.status == "blocked":
            raise ClientBlockedError(f"Client {client_id} is blocked")

        if client.verify_password(password):
            client.failed_attempts = 0
            client.log_activity("Successful auth")
            self.audit_log.info("auth_success", f"Auth ok for {client_id}", client_id=client_id)
            return True

        client.failed_attempts += 1
        self.audit_log.warning(
            "auth_failed",
            f"Auth failed for {client_id} "
            f"({client.failed_attempts}/{self.MAX_FAILED_ATTEMPTS})",
            client_id=client_id,
            attempt=client.failed_attempts,
        )
        client.log_activity(
            f"Authentication failed ({client.failed_attempts}/{self.MAX_FAILED_ATTEMPTS})"
        )

        if client.failed_attempts >= self.MAX_FAILED_ATTEMPTS:
            client.status = "blocked"
            self.audit_log.critical(
                "client_blocked",
                f"Client {client_id} blocked after {self.MAX_FAILED_ATTEMPTS} failed attempts",
                client_id=client_id,
            )
            client.mark_suspicious(
                f"Exceeded login attempts ({self.MAX_FAILED_ATTEMPTS})"
            )
            raise ClientBlockedError(
                f"Client {client_id} was blocked after "
                f"{self.MAX_FAILED_ATTEMPTS} failed attempts"
            )

        raise AuthenticationError(
            f"Wrong password. Attempts left: "
            f"{self.MAX_FAILED_ATTEMPTS - client.failed_attempts}"
        )

    # ---------- Счета ----------
    def open_account(
        self, client_id: str, account_type: str = "basic", **kwargs
    ) -> BankAccount:
        self._check_time()
        client = self._get_client(client_id)

        if client.status == "blocked":
            raise ClientBlockedError(f"Client {client_id} is blocked")

        if account_type not in self.ACCOUNT_TYPES:
            raise InvalidOperationError(
                f"Unknown account type: {account_type}. "
                f"Available: {', '.join(self.ACCOUNT_TYPES)}"
            )

        account_cls = self.ACCOUNT_TYPES[account_type]
        # Фикс 7: прокидываем now_provider в счёт
        kwargs.setdefault("now_provider", self._now)
        account = account_cls(owner=client.full_name, **kwargs)

        self.accounts[account.account_id] = account
        self.account_owners[account.account_id] = client_id
        client.link_account(account.account_id)
        client.log_activity(f"Opened account {account.account_id} ({account_type})")

        # Фикс 1: account_type вместо type
        self.audit_log.info(
            "account_opened",
            f"Opened {account_type} account {account.account_id} for {client_id}",
            account_id=account.account_id,
            client_id=client_id,
            account_type=account_type,
        )
        return account

    def close_account(self, account_id: str) -> None:
        self._check_time()
        account = self._get_account(account_id)

        # Фикс 2: сначала close, потом pop
        account.close()

        client_id = self.account_owners.pop(account_id, None)
        if client_id and client_id in self.clients:
            self.clients[client_id].unlink_account(account_id)

        # Фикс 1: без type / client_id в f-string
        self.audit_log.info(
            "account_closed",
            f"Closed account {account_id}",
            account_id=account_id,
            client_id=client_id,
        )

    def freeze_account(self, account_id: str) -> None:
        self._check_time()
        self._get_account(account_id).freeze()
        client_id = self.account_owners.get(account_id)
        self.audit_log.warning(
            "account_frozen",
            f"Frozen account {account_id}",
            account_id=account_id,
            client_id=client_id,
        )

    def unfreeze_account(self, account_id: str) -> None:
        self._check_time()
        self._get_account(account_id).unfreeze()
        client_id = self.account_owners.get(account_id)
        self.audit_log.info(
            "account_unfrozen",
            f"Unfrozen account {account_id}",
            account_id=account_id,
            client_id=client_id,
        )

    # ---------- Финансовые операции (ручные) ----------
    def deposit(
        self, client_id: str, password: str, account_id: str, amount: float
    ) -> None:
        self._check_time()
        self.authenticate_client(client_id, password)
        client = self._get_client(client_id)
        self._ensure_owner(client, account_id)

        self._get_account(account_id).deposit(amount)
        client.log_activity(f"Deposit {amount} to {account_id}")

    def withdraw(
        self, client_id: str, password: str, account_id: str, amount: float
    ) -> None:
        self._check_time()
        self.authenticate_client(client_id, password)
        client = self._get_client(client_id)
        self._ensure_owner(client, account_id)

        self._get_account(account_id).withdraw(amount)
        client.log_activity(f"Withdraw {amount} from {account_id}")

    # ---------- Поиск и аналитика ----------
    def search_accounts(
        self, query: str = "", status: str | None = None
    ) -> list[BankAccount]:
        q = query.lower()
        result = []
        for acc in self.accounts.values():
            if q and q not in acc.account_id.lower() and q not in acc.owner.lower():
                continue
            if status and acc.status != status:
                continue
            result.append(acc)
        return result

    def get_total_balance(self, client_id: str | None = None) -> float:
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

    # ---------- Переводы ----------
    def calculate_external_commission(
        self,
        src_id: str,
        dst_id: str,
        amount: float,
        base: float = 0.0,
        rate: float = 0.01,
    ) -> float:
        src_owner = self.account_owners.get(src_id)
        if src_owner is None:
            raise AccountNotFoundError(f"Account {src_id} not found")
        dst_owner = self.account_owners.get(dst_id)
        if dst_owner is None:
            raise AccountNotFoundError(f"Account {dst_id} not found")

        if src_owner == dst_owner:
            return base
        return round(base + amount * rate, 2)

    def create_transfer(
        self,
        from_id: str,
        to_id: str,
        amount: float,
        currency: str,
        base_commission: float = 0.0,
        external_rate: float = 0.01,
        **tx_kwargs,
    ) -> Transaction:
        commission = self.calculate_external_commission(
            from_id, to_id, amount, base=base_commission, rate=external_rate
        )
        # Фикс 7: прокидываем now_provider в транзакцию
        tx_kwargs.setdefault("now_provider", self._now)
        return Transaction(
            "transfer", amount, currency,
            from_account_id=from_id,
            to_account_id=to_id,
            commission=commission,
            **tx_kwargs,
        )

    # ---------- Отчёты аудита (делегируем в AuditReporter) ----------
    def report_suspicious_operations(
        self, since: datetime | None = None, until: datetime | None = None
    ) -> dict:
        return self.reporter.report_suspicious_operations(since=since, until=until)

    def report_client_risk_profile(self, client_id: str) -> dict:
        return self.reporter.report_client_risk_profile(client_id)

    def report_error_statistics(self, since: datetime | None = None) -> dict:
        return self.reporter.report_error_statistics(since=since)

    def __str__(self) -> str:
        return (
            f"Bank(clients={len(self.clients)}, accounts={len(self.accounts)}, "
            f"audit_entries={len(self.audit_log)})"
        )
#day4
class Transaction:
    VALID_CURRENCIES = {"RUB", "USD", "EUR", "KZT", "CNY"}
    VALID_TYPES = {"deposit", "withdraw", "transfer"}
    VALID_STATUSES = {"pending", "processing", "completed", "failed", "cancelled"}

    def __init__(
        self,
        transaction_type: str,
        amount: float,
        currency: str,
        from_account_id: str | None = None,
        to_account_id: str | None = None,
        commission: float = 0.0,
        transaction_id: str | None = None,
        max_attempts: int = 3,
        priority: int = 5,
        scheduled_at: datetime | None = None,
        now_provider=None,
    ):
        # --- Валидация ---
        if transaction_type not in self.VALID_TYPES:
            raise InvalidOperationError(
                f"Invalid type. Valid options are: {', '.join(self.VALID_TYPES)}"
            )
        if currency not in self.VALID_CURRENCIES:
            raise InvalidOperationError(
                f"Invalid currency. Valid options are: {', '.join(self.VALID_CURRENCIES)}"
            )
        validate_amount(amount)
        if commission < 0:
            raise InvalidOperationError("Commission cannot be negative")
        if not (1 <= priority <= 10):
            raise InvalidOperationError("Priority must be from 1 to 10")
        self._validate_parties(transaction_type, from_account_id, to_account_id)

      
        self.id = str(uuid.uuid4())[:8] if transaction_id is None else transaction_id

        
        self.type = transaction_type
        self.amount = amount
        self.currency = currency
        self.commission = commission
        self.from_account_id = from_account_id
        self.to_account_id = to_account_id

       
        self.status = "pending"
        self.failure_reason: str | None = None
        self.failure_code: str | None = None
        self.attempts = 0
        self.max_attempts = max_attempts

        
        self._now = now_provider or datetime.now
        self.created_at = self._now()
        self.processed_at: datetime | None = None
        self.scheduled_at = scheduled_at
        self.priority = priority


    @staticmethod
    def _validate_parties(tx_type: str, from_id: str | None, to_id: str | None) -> None:
        if tx_type == "transfer":
            if not from_id or not to_id:
                raise InvalidOperationError(
                    "transfer requires both from_account_id and to_account_id"
                )
            if from_id == to_id:
                raise InvalidOperationError("Cannot transfer to the same account")
        elif tx_type == "deposit":
            if from_id is not None or not to_id:
                raise InvalidOperationError("deposit requires only to_account_id")
        elif tx_type == "withdraw":
            if not from_id or to_id is not None:
                raise InvalidOperationError("withdraw requires only from_account_id")

    
    def mark_processing(self) -> None:
        self._require_status("pending")
        self.status = "processing"

    def mark_completed(self) -> None:
        self._require_status("processing")
        self.status = "completed"
        self.failure_reason = None
        self.failure_code = None
        self.processed_at = self._now()

    def mark_failed(self, reason: str, code: str) -> None:
        if not reason:
            raise InvalidOperationError("failure_reason обязателен для failed")
        self._require_status("processing")
        self.status = "failed"
        self.failure_code = code
        self.failure_reason = reason
        self.processed_at = self._now()

    def mark_pending_for_retry(self) -> None:
        self._require_status("processing")
        self.status = "pending"
        self.processed_at = None
        

    def cancel(self) -> None:
        self._require_status("pending")
        self.status = "cancelled"
        self.processed_at = self._now()
        self.failure_reason = None           # ← добавили
        self.failure_code = None

    def _require_status(self, expected: str) -> None:
        if self.status != expected:
            raise InvalidOperationError(
                f"Недопустимый переход: {self.status} -> (ожидался {expected})"
            )


    @property
    def total_debit(self) -> float:
        """Сколько списать с отправителя: amount + commission."""
        return self.amount + self.commission

    def __str__(self) -> str:
        reason = f" | Reason: {self.failure_reason}" if self.failure_reason else ""
        return (
            f"Tx {self.id} [{self.type}] {self.amount} {self.currency} "
            f"(commission {self.commission}) | "
            f"{self.from_account_id or '—'} -> {self.to_account_id or '—'} | "
            f"{self.status.upper()}{reason}"
        )

class TransactionQueue():
    def __init__(self, now_provider=None):
        self._now = now_provider or datetime.now
        self._pending: list[tuple[int, int, "Transaction"]] = []
        self._scheduled: list[tuple[float, int, "Transaction"]] = []
        self._failed: list[Transaction] = []
        self._index: dict[str, "Transaction"] = {}
        self._seq: int = 0

    def enqueue(self, tx: "Transaction") -> None:
        if tx.id in self._index:
            raise InvalidOperationError(f"Doubles id: {tx.id}")
        self._index[tx.id] = tx
        if tx.scheduled_at and tx.scheduled_at > self._now():
            heapq.heappush(
                self._scheduled,
                (tx.scheduled_at.timestamp(), self._next_seq(), tx),
            )
        else:
            heapq.heappush(self._pending, (tx.priority, self._next_seq(), tx))

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def dequeue(self) -> "Transaction | None":
        self._promote_ready()
        while self._pending:
            _, _, tx = heapq.heappop(self._pending)
            if tx.status == "cancelled":
                self._index.pop(tx.id, None)   
                continue
            self._index.pop(tx.id, None)       
            return tx
        return None

    def _promote_ready(self) -> None:
        """Перелить созревшие scheduled -> pending."""
        now_ts = self._now().timestamp()
        while self._scheduled and self._scheduled[0][0] <= now_ts:
            _, _, tx = heapq.heappop(self._scheduled)
            if tx.status == "cancelled":       # уже отменена — не переносим
                continue
            heapq.heappush(self._pending, (tx.priority, self._next_seq(), tx))

    def cancel(self, tx_id: str) -> bool:
        tx = self._index.get(tx_id)
        if tx is None or tx.status != "pending":
            return False
        tx.cancel()                             # status="cancelled"
        return True
    
    def move_to_failed(self, tx: "Transaction") -> None:
        if any(t.id == tx.id for t in self._failed):
            return
        self._failed.append(tx)

    @property
    def failed(self) -> list["Transaction"]:
        """Read-only доступ к dead-letter (для тестов и аналитики)."""
        return list(self._failed) 

    def __len__(self) -> int:
        return sum(
            1 for _, _, tx in self._pending if tx.status != "cancelled"
        )

    def next_scheduled_time(self) -> "datetime | None":
        """Когда ближайшая отложенная станет готовой (для логов/тестов)."""
        if not self._scheduled:
            return None
        ts, _, _ = self._scheduled[0]
        return datetime.fromtimestamp(ts)

    def peek_failed(self) -> list["Transaction"]:
        """Список упавших (в dead-letter)."""
        return list(self._failed)
    
        


class TransactionProcessor:
    RETRYABLE_ERRORS = (AccountFrozenError,)

    def __init__(self, bank, queue, converter: "CurrencyConverter", logger=None, risk_check: bool = True):
        self.bank = bank
        self.queue = queue
        self.converter = converter
        self.risk_check = risk_check
        self.log = logger or logging.getLogger(__name__)

    def process_one(self) -> bool:
        
        tx = self.queue.dequeue()
        if tx is None:
            return False
        return self._process_transaction(tx)

    def process_all(self, max_iterations: int = 1000) -> dict:
        stats = {"processed": 0, "succeeded": 0, "failed": 0, "retried": 0}
        while stats["processed"] < max_iterations:
            if not self.queue:                
                break
            success = self.process_one()
            stats["processed"] += 1
            stats["succeeded" if success else "failed"] += 1
        return stats

   
    def _process_transaction(self, tx: "Transaction") -> bool:
        tx.mark_processing()
    # client_id нужен и для риска, и для аудита
        client_id = (
            self.bank.account_owners.get(tx.from_account_id)
            or self.bank.account_owners.get(tx.to_account_id)
        )

        try:
            if self.risk_check:
                self.bank.analyze_transaction_risk(tx)   # HIGH → SuspiciousTransactionError

            self._dispatch(tx)
            tx.mark_completed()
            self.log.info(f"Tx completed: {tx.id}")

        # Audit: обязателен для _check_frequency и отчётов
            self.bank.audit_log.info(
                "transaction_completed",
                f"Tx {tx.id} completed",
                transaction_id=tx.id,
                client_id=client_id,
                amount=tx.amount,
                currency=tx.currency,
                )
            return True
        except Exception as exc:
            return self._handle_error(tx, exc, client_id)


    def _handle_error(self, tx: "Transaction", exc: Exception, client_id: str | None) -> bool:
        tx.attempts += 1
        reason = self._humanize(exc)
        code = self._code_of(exc)

        if self.should_retry(exc) and tx.attempts < tx.max_attempts:
            tx.failure_code = code
            tx.failure_reason = reason
            tx.mark_pending_for_retry()
            self.queue.enqueue(tx)
            self.log.warning(f"Tx retry {tx.attempts}/{tx.max_attempts}: {tx.id} — {exc}")
            self.bank.audit_log.warning(
                "transaction_retry",
                f"Retry {tx.attempts}/{tx.max_attempts}: {tx.id}",
                transaction_id=tx.id,
                client_id=client_id,
                attempt=tx.attempts,                     
                max_attempts=tx.max_attempts,
            )
        else:
            tx.mark_failed(reason, code=code)
            self.bank.audit_log.error(
                "transaction_failed",
                f"Transaction {tx.id} failed",
                transaction_id=tx.id,
                client_id=client_id,
                failure_code=tx.failure_code,            
                reason=tx.failure_reason,
            )   
            self.queue.move_to_failed(tx)
            self.log.error(f"Tx failed: {tx.id} | {type(exc).__name__}: {exc}")
        return False

    def should_retry(self, exc: Exception) -> bool:
        return isinstance(exc, self.RETRYABLE_ERRORS)


    def _dispatch(self, tx: "Transaction") -> None:
        handlers = {
            "transfer": self._execute_transfer,
            "deposit":  self._execute_deposit,
            "withdraw": self._execute_withdraw,
        }
        handler = handlers.get(tx.type)
        if handler is None:
            raise InvalidOperationError(f"{tx.type}")
        handler(tx)


    def _execute_transfer(self, tx: "Transaction") -> None:
    # ФАЗА 1: проверки
        src = self._get_active_account(tx.from_account_id)
        dst = self._get_active_account(tx.to_account_id)

        can, reason = src.can_send(tx.total_debit)          
        if not can:
            raise InsufficientFundsError(reason)

        converted = self.converter.convert(tx.amount, tx.currency, dst.currency)

    # ФАЗА 2: изменения
        src._balance -= tx.total_debit
        dst._balance += converted

    def _execute_deposit(self, tx: "Transaction") -> None:
        dst = self._get_active_account(tx.to_account_id)
        dst._balance += tx.amount

    def _execute_withdraw(self, tx: "Transaction") -> None:
        src = self._get_active_account(tx.from_account_id)
        if tx.total_debit > src.balance:
            raise InsufficientFundsError(...)
        src._balance -= tx.total_debit

    def _get_active_account(self, account_id: str) -> "BankAccount":
        acc = self.bank.accounts.get(account_id)
        if acc is None:
            raise AccountNotFoundError(f"Account {account_id} not found")
        acc.check_status()                
        return acc


    def _code_of(self, exc: Exception) -> str:
        for cls, code in self.ERROR_CODES.items():
            if isinstance(exc, cls):
                return code
        return "unknown_error"

    def _humanize(self, exc: Exception) -> str:
        return str(exc) or type(exc).__name__

    ERROR_CODES = {
        InsufficientFundsError: "insufficient_funds",
        AccountFrozenError:     "account_frozen",
        AccountClosedError:     "account_closed",
        AccountNotFoundError:   "account_not_found",
        InvalidOperationError:  "invalid_operation",
        ClientBlockedError:     "client_blocked",
        SuspiciousTransactionError: "risk_blocked",
    }
#day5
class AuditLevel(Enum):
  INFO = 1
  WARNING = 2
  ERROR = 3
  CRITICAL = 4


class AuditEntry:
    def __init__(self,level: AuditLevel, event_type: str, message: str,client_id: str | None = None,
                 account_id: str | None = None, transaction_id: str | None = None, metadata: dict| None = {},timestamp: datetime | None = None, now_provider = None ):
        if level not in AuditLevel:
            raise InvalidOperationError(f"AuditLevel should be one of {AuditLevel}")
        self.level = level
        self.event_type = event_type
        self.message = message
        self.client_id = client_id
        self.account_id = account_id
        self.transaction_id = transaction_id
        self.metadata = metadata
        if not event_type or not isinstance(event_type, str):
            raise InvalidOperationError("event_type must be a non-empty string")
        if not message or not isinstance(message, str):
            raise InvalidOperationError("message must be a non-empty string")
        if metadata is not None and not isinstance(metadata, dict):
            raise InvalidOperationError("metadata must be a dict or None")
        self.id = str(uuid.uuid4()) if id is None else id
        self._now = now_provider or datetime.now
        self.timestamp = timestamp if timestamp is not None else self._now()


    def audit_entry_to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "level": self.level.name,
            "client_id": self.client_id,
            "account_id": self.account_id,
            "transaction_id": self.transaction_id,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "metadata": self.metadata
        }
    def audit_entry_to_json(self) -> str:
        return json.dumps(self.audit_entry_to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "AuditEntry":
        return cls(
            message=str(d["message"]),
            event_type=str(d["event_type"]),
            level=AuditLevel[d["level"]],
            timestamp=datetime.fromisoformat(d["timestamp"]),

            metadata=d.get("metadata"),
            client_id=d.get("client_id"),
            account_id=d.get("account_id"),
            transaction_id=d.get("transaction_id"),
        )
    def __str__(self):
        return (
            f"Event type {self.event_type} | {self.level} | "
            f"Message: {self.message.upper()} | Account: {self.account_id} | "
            f"Client: {self.client_id} | {self.transaction_id}"
            f"Metadata: {self.metadata} | {self.timestamp}"
        )
class AuditLog:
    def __init__(
        self,
        log_file: str | Path | None = None,
        max_entries: int = 10000,
        now_provider=None,
    ):
        if max_entries <= 0:
            raise InvalidOperationError(
                f"max_entries must be > 0, got {max_entries}"
            )
        self._entries: deque[AuditEntry] = deque(maxlen=max_entries)
        self._log_file: Path | None = Path(log_file) if log_file else None
        self._now = now_provider or datetime.now
        self.max_entries = max_entries

    
    def log(self,
        level: AuditLevel,
        event_type: str,
        message: str,
        *,
        client_id: str | None = None,
        account_id: str | None = None,
        transaction_id: str | None = None,
        **metadata,
    ) -> AuditEntry:
        
        entry = AuditEntry(
            level=level,
            event_type=event_type,
            message=message,
            client_id=client_id,
            account_id=account_id,
            transaction_id=transaction_id,
            metadata=metadata,
            now_provider=self._now,
        )
        
        self._entries.append(entry)
        if self._log_file is not None:
            self._write_to_file(entry)
        return entry

    def info(self, event_type: str, message: str, **ctx) -> AuditEntry:
        return self.log(AuditLevel.INFO, event_type, message, **ctx)

    def warning(self, event_type: str, message: str, **ctx) -> AuditEntry:
        return self.log(AuditLevel.WARNING, event_type, message, **ctx)

    def error(self, event_type: str, message: str, **ctx) -> AuditEntry:
        return self.log(AuditLevel.ERROR, event_type, message, **ctx)

    def critical(self, event_type: str, message: str, **ctx) -> AuditEntry:
        return self.log(AuditLevel.CRITICAL, event_type, message, **ctx)

    
    def get_entries(
        self,
        *,
        level: AuditLevel | None = None,
        event_type: str | None = None,
        client_id: str | None = None,
        transaction_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int | None = None,
        reverse: bool = False,
    ) -> list[AuditEntry]:
        result: list[AuditEntry] = []
        for entry in self._entries:
            if level is not None and entry.level != level:
                continue
            if event_type is not None and entry.event_type != event_type:
                continue
            if client_id is not None and entry.client_id != client_id:
                continue
            if transaction_id is not None and entry.transaction_id != transaction_id:
                continue
            if since is not None and entry.timestamp < since:
                continue
            if until is not None and entry.timestamp > until:
                continue
            result.append(entry)

        if limit is not None:
            result = result[-limit:]  # N самых свежих (в хронологическом порядке)
        if reverse:
            result.reverse()           # новые сначала
        return result

    
    def count_by_level(self) -> dict[AuditLevel, int]:
        """Все 4 уровня (отсутствующие — 0), удобно для отчётов."""
        counter = Counter(entry.level for entry in self._entries)
        return {level: counter.get(level, 0) for level in AuditLevel}

    def count_by_event_type(self) -> dict[str, int]:
        """Только встретившиеся event_type (без нулей)."""
        return dict(Counter(entry.event_type for entry in self._entries))

    
    def clear_memory(self) -> None:
        """Очистить память. Файл не трогаем (append-only, история важна)."""
        self._entries.clear()

    def export_to_file(self, path: str | Path) -> None:
        """Выгрузить все записи из памяти в файл (перезапись)."""
        p = Path(path)
        if p.parent != Path("."):
            p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            for entry in self._entries:
                f.write(entry.audit_entry_to_json() + "\n")

    def __len__(self) -> int:
        return len(self._entries)

    def _write_to_file(self, entry: AuditEntry) -> None:
        """Записать одну запись. Не пробрасывать OSError — аудит не бизнес-логика."""
        try:
            if self._log_file.parent != Path("."):
                self._log_file.parent.mkdir(parents=True, exist_ok=True)
            with self._log_file.open("a", encoding="utf-8") as f:
                f.write(entry.audit_entry_to_json() + "\n")
        except OSError as exc:
            logger.error(
                "AuditLog: failed to write entry %s to %s: %s",
                entry.id, self._log_file, exc,
            )
class RiskLevel(Enum):
  LOW = 1
  MEDIUM = 2
  HIGH = 3
  def __str__(self) -> str:
        return self.name

class RiskEvent:
    def __init__(self, transaction_id: str, client_id: str | None,reasons: list[str], level: RiskLevel, now_provider:None,
                 timestamp: datetime| None = None):
        self.transaction_id = transaction_id
        self.client_id = client_id
        self.reasons = list(reasons)
        self.level = level
        self.score = len(reasons)
        self._now = now_provider or datetime.now
        self.timestamp = timestamp if timestamp is not None else self._now()

    def should_block(self) -> bool:
        return self.level == RiskLevel.HIGH

    def risk_event_to_dict(self) -> dict:
        return {
                    "transaction_id": self.transaction_id,
                    "client_id": self.client_id,
                    "reasons": self.reasons,
                    "level": self.level.name,
                    "timestamp": self.timestamp.isoformat(),
                    "score": self.score
                }
    def __str__(self) -> str:
        reasons = f" | {', '.join(self.reasons)}" if self.reasons else ""
        return (
            f"RiskEvent(tx={self.transaction_id}, client={self.client_id}, "
            f"level={self.level.name}, score={self.score}{reasons})"
        )

    def __repr__(self) -> str:
        return (
            f"RiskEvent(tx={self.transaction_id!r}, "
            f"level={self.level.name}, score={self.score})"
        )
class RiskAnalyzer:
    
    DEFAULT_THRESHOLDS = {
        "large_amount": {
            "RUB": 100_000, "USD": 1_000, "EUR": 1_000,
            "KZT": 500_000, "CNY": 7_000,
        },
        "frequency_window_minutes": 10,
        "frequency_max_operations": 5,
        "night_hours": (22, 6),          
        "new_account_days": 30,
    }

    def __init__(
        self,
        bank=None,                        
        audit_log=None,                   
        thresholds: dict | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ):
        self.bank = bank
        self.audit_log = audit_log
        self._now = now_provider or datetime.now
        self.thresholds = self._build_thresholds(thresholds)

    def _build_thresholds(self, overrides: dict | None) -> dict:
        result = {
            "large_amount": dict(self.DEFAULT_THRESHOLDS["large_amount"]),
            "frequency_window_minutes": self.DEFAULT_THRESHOLDS["frequency_window_minutes"],
            "frequency_max_operations": self.DEFAULT_THRESHOLDS["frequency_max_operations"],
            "night_hours": self.DEFAULT_THRESHOLDS["night_hours"],
            "new_account_days": self.DEFAULT_THRESHOLDS["new_account_days"],
        }
        if not overrides:
            return result

        if "large_amount" in overrides:
            result["large_amount"].update(overrides["large_amount"])

        if "frequency_window_minutes" in overrides:
            v = overrides["frequency_window_minutes"]
            if v <= 0:
                raise InvalidOperationError("frequency_window_minutes must be > 0")
            result["frequency_window_minutes"] = v

        if "frequency_max_operations" in overrides:
            v = overrides["frequency_max_operations"]
            if v < 1:
                raise InvalidOperationError("frequency_max_operations must be >= 1")
            result["frequency_max_operations"] = v

        if "night_hours" in overrides:
            v = overrides["night_hours"]
            if (not isinstance(v, tuple) or len(v) != 2
                    or not all(isinstance(x, int) and 0 <= x <= 24 for x in v)):
                raise InvalidOperationError(
                    "night_hours must be tuple[int, int] with values in 0..24"
                )
            result["night_hours"] = v

        if "new_account_days" in overrides:
            v = overrides["new_account_days"]
            if v < 0:
                raise InvalidOperationError("new_account_days must be >= 0")
            result["new_account_days"] = v

        return result
    def analyze_transaction(self, tx, client_id: str | None = None) -> RiskEvent:
        if client_id is None:
            client_id = self._resolve_client_id(tx)

        reasons: list[str] = []

        r = self._check_large_amount(tx)
        if r: reasons.append(r)

        r = self._check_frequency(tx, client_id)
        if r: reasons.append(r)

        r = self._check_new_account(tx)
        if r: reasons.append(r)

        r = self._check_night_time(tx)
        if r: reasons.append(r)

        level = self._level_for(len(reasons))
        return RiskEvent(
            transaction_id=tx.id,
            client_id=client_id,
            reasons=reasons,
            level=level,
            now_provider=self._now,
        )
    @staticmethod
    def _level_for(reasons_count: int) -> RiskLevel:
        if reasons_count == 0:
            return RiskLevel.LOW
        if reasons_count <= 2:
            return RiskLevel.MEDIUM
        return RiskLevel.HIGH

    def _check_large_amount(self, tx) -> str | None:
        threshold = self.thresholds["large_amount"].get(tx.currency)
        if threshold is None:
            return None                 # неизвестная валюта — правило не применяется
        if tx.amount > threshold:
            return f"large amount: {tx.amount} > {threshold} {tx.currency}"
        return None

    def _check_frequency(self, tx, client_id: str | None) -> str | None:
        if self.audit_log is None or client_id is None:
            return None
        since = self._now() - timedelta(
            minutes=self.thresholds["frequency_window_minutes"]
        )
        recent = self.audit_log.get_entries(
            event_type="transaction_completed",     # ← НЕ считаем текущую
            client_id=client_id,
            since=since,
        )
        limit = self.thresholds["frequency_max_operations"]
        if len(recent) >= limit:
            return (
                f"frequent: {len(recent)} ops in "
                f"{self.thresholds['frequency_window_minutes']} min (limit {limit})"
            )
        return None

    def _check_new_account(self, tx) -> str | None:
        if self.bank is None or tx.to_account_id is None:
            return None
        acc = getattr(self.bank, "accounts", {}).get(tx.to_account_id)
        if acc is None:
            return None
        created_at = getattr(acc, "created_at", None)
        if created_at is None:
            return None
        age_days = (self._now() - created_at).days
        limit = self.thresholds["new_account_days"]
        if age_days < limit:
            return f"new account: opened {age_days} days ago (limit {limit})"
        return None

    def _check_night_time(self, tx) -> str | None:
        start, end = self.thresholds["night_hours"]
        now = self._now()
        if self._in_window(now.hour, start, end):
            return f"night operation at {now:%H:%M}"
        return None
    
    @staticmethod
    def _in_window(hour: int, start: int, end: int) -> bool:
        """Попадает ли hour в окно [start, end).

        start == end     → окно пустое (правило отключено)
        start <  end     → обычное окно (например, 9..17)
        start >  end     → окно через полночь (например, 22..6)
        """
        if start == end:
            return False
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    def _resolve_client_id(self, tx) -> str | None:
        """Определить client_id по счёту-источнику (или получателю для deposit)."""
        if self.bank is None:
            return None
        account_id = tx.from_account_id or tx.to_account_id
        if account_id is None:
            return None

        owners = getattr(self.bank, "account_owners", None)
        if owners is not None:
            return owners.get(account_id)

        for client in getattr(self.bank, "clients", {}).values():
            if account_id in getattr(client, "account_ids", []):
                return client.client_id
        return None


class AuditReporter:

    def __init__(self, audit_log: AuditLog, risk_analyzer=None, bank=None):
        self.audit_log = audit_log
        self.risk_analyzer = risk_analyzer
        self.bank = bank

    def report_suspicious_operations(self, since: datetime | None = None, until: datetime | None = None) -> dict:
        alerts = self.audit_log.get_entries(
            event_type="risk_alert", since=since, until=until)
        blocked = self.audit_log.get_entries(
            event_type="risk_blocked", since=since, until=until)

        by_client: dict[str, dict] = defaultdict(
            lambda: {"alerts": [], "blocked": []})

        def _to_dict(e: AuditEntry) -> dict:
            return {
                "tx_id": e.transaction_id,
                "risk_level": e.metadata.get("risk_level", "unknown"),
                "reasons": e.metadata.get("reasons", []),
                "timestamp": e.timestamp.isoformat(),
            }

        for e in alerts:
            by_client[e.client_id or "unknown"]["alerts"].append(_to_dict(e))
        for e in blocked:
            by_client[e.client_id or "unknown"]["blocked"].append(_to_dict(e))

        result = {}
        for cid, data in by_client.items():
            name = None
            if self.bank and cid in self.bank.clients:
                name = self.bank.clients[cid].full_name
            result[cid] = {"client_name": name, **data}

        return {
            "period": {
                "since": since.isoformat() if since else None,
                "until": until.isoformat() if until else None,
            },
            "total_alerts": len(alerts),
            "total_blocked": len(blocked),
            "by_client": result,
        }

    def report_client_risk_profile(self, client_id: str) -> dict:
        if self.bank and client_id not in self.bank.clients:
            from utils import ClientNotFoundError
            raise ClientNotFoundError(f"Client {client_id} not found")

        alerts = self.audit_log.get_entries(
            event_type="risk_alert", client_id=client_id
        )
        blocked = self.audit_log.get_entries(
            event_type="risk_blocked", client_id=client_id
        )

        distribution = {"low": 0, "medium": 0, "high": 0}
        reasons_counter: Counter[str] = Counter()
        for e in alerts + blocked:
            lvl = e.metadata.get("risk_level", "")
            if lvl in distribution:
                distribution[lvl] += 1
            for r in e.metadata.get("reasons", []):
                reasons_counter[r] += 1

        name = None
        if self.bank and client_id in self.bank.clients:
            name = self.bank.clients[client_id].full_name

        last = self.audit_log.get_entries(
            client_id=client_id, limit=1, reverse=True
        )

        return {
            "client_id": client_id,
            "client_name": name,
            "risk_distribution": distribution,
            "blocked_count": len(blocked),
            "top_reasons": [
                {"reason": r, "count": c}
                for r, c in reasons_counter.most_common(5)
            ],
            "last_activity": last[0].timestamp.isoformat() if last else None,
        }

    def report_error_statistics(self, since: datetime | None = None) -> dict:
        errors = self.audit_log.get_entries(
            level=AuditLevel.ERROR, since=since
        )
        by_code = Counter(
            e.metadata.get("failure_code", "unknown") for e in errors
        )
        by_event = Counter(e.event_type for e in errors)

        return {
            "period": {"since": since.isoformat() if since else None},
            "total_errors": len(errors),
            "by_code": dict(by_code),
            "by_event_type": dict(by_event),
        }