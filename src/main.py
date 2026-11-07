from models import BankAccount
from utils import AccountFrozenError, InsufficientFundsError

def run_demo():
    print("--- 1. Creating an active account ---")
    active_acc = BankAccount(owner="Иван Иванов", balance=1000.0, currency="RUB")
    print(active_acc)

    print("\n--- 2. Valid operations ---")
    active_acc.deposit(500.0)
    print(f"Deposit 500: {active_acc}")
    
    active_acc.withdraw(200.0)
    print(f"Withdraw 200: {active_acc}")

    print("\n--- 3. Frozen account ---")
    frozen_acc = BankAccount(owner="Петр Петров", balance=50.0, currency="USD")
    frozen_acc.status = "frozen" 
    print(frozen_acc)

    
    print("\n--- 4. frozen account operations ---")
    try:
        frozen_acc.deposit(100.0)
    except AccountFrozenError as e:
        print(f"Error: {e}")

    try:
        frozen_acc.withdraw(10.0)
    except AccountFrozenError as e:
        print(f"Error: {e}")

    print("\n--- 5. Insufficient funds ---")
    try:
        active_acc.withdraw(10000.0)
    except InsufficientFundsError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_demo()