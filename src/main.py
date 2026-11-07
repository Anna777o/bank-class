from models import BankAccount, SavingsAccount, PremiumAccount, InvestmentAccount
from utils import AccountFrozenError, InsufficientFundsError, InvalidOperationError

def run_demo():
    #day1
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
    #day2
    # 1. SavingsAccount
    saving_acc = SavingsAccount(owner="Анна", balance=1000.0, min_balance=500.0, interest_rate=0.05)
    print(saving_acc)

    try:
        saving_acc.withdraw(1000.0)
    except InvalidOperationError as e:
        print(f"Expected error {e}")
    saving_acc.withdraw(300.0)
    saving_acc.apply_monthly_interest()
    print(saving_acc)

    # 2. PremiumAccount
    premium_acc = PremiumAccount(owner="Олег", balance=1000.0, overdraft_limit=500.0, commission=50.0)
    print(premium_acc)
    premium_acc.withdraw(1200.0)
    print(premium_acc)
    
    try:
        premium_acc.withdraw(500.0)
    except InvalidOperationError as e:
        print(f"Expected error {e}")
    # 3. InvestmentAccount
    invest_acc = InvestmentAccount(owner="Мария", balance=5000.0, currency="USD")
    print(invest_acc)
    invest_acc.invest("stocks", 2000.0)
    invest_acc.invest("etf", 1000.0)
    print(invest_acc)

    growth_rates = {"stocks": 0.10, "bonds": 0.04, "etf": 0.07}
    print(growth_rates)
    projected = invest_acc.project_yearly_growth(growth_rates)
    print(f"Expected in the end of the year: {projected:.2f} USD")
    print(f" Expected growth: {projected - 3000.0:.2f} USD")

if __name__ == "__main__":
    run_demo()