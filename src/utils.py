#day1
class BankGeneralError(Exception):
    """Base class for all bank-related exceptions."""
    pass
class AccountFrozenError(BankGeneralError):
    """Raised when an operation is attempted on a frozen account."""
    pass
class AccountClosedError(BankGeneralError):
    """Raised when an operation is attempted on a closed account."""
    pass
class InvalidOperationError(BankGeneralError):
    """Raised when an invalid operation is attempted on an account."""
    pass
class InsufficientFundsError(BankGeneralError):
    """Raised when an account has insufficient funds for a withdrawal."""
    pass
def validate_amount(amount: float) -> None:
    """Validate that the amount is a positive number."""
    print(f"DEBUG | amount={amount!r} | type={type(amount)} | int={int} | float={float} | isinstance={isinstance(amount, (int, float))}")
    if not isinstance(amount, (int, float)):
        raise InvalidOperationError("Сумма должна быть числом.")
    if amount <= 0:
        raise InvalidOperationError("Amount must be a positive number.")
#day3

class ClientNotAdultError(InvalidOperationError):
    """Validate that client is 18 years old or older"""
    pass

class ClientNotFoundError(BankGeneralError):
    """Client is not found in system"""
    pass

class AccountNotFoundError(BankGeneralError):
    """Client account is not found in system"""
    pass

class ClientBlockedError(BankGeneralError):
    """Client is blocked"""
    pass

class AuthenticationError(BankGeneralError):
    """Client authentication failed"""
    pass

class RestrictedTimeError(BankGeneralError):
    """Bank operation is prohibited during night"""
    pass
class SuspiciousTransactionError(BankGeneralError):
    pass
