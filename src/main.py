from models import BankAccount, SavingsAccount, PremiumAccount, InvestmentAccount, Bank, Client, Transaction, TransactionQueue, TransactionProcessor
from utils import (
    ClientNotAdultError, ClientBlockedError, AuthenticationError,
    RestrictedTimeError, AccountNotFoundError, ClientNotAdultError, AccountClosedError,
    AccountFrozenError, InvalidOperationError, InsufficientFundsError, validate_amount
)
import currency_converter

import logging
from datetime import date, datetime
import hashlib 
def run_demo():
    logging.basicConfig(level=logging.INFO)
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
        premium_acc.withdraw(50.0)
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


#day3
        
    bank = Bank(now_provider=lambda: datetime(2024, 1, 1, 12, 0))

    # --- age check
    print("--- 1. Age check ---")
    try:
        Client("Minor", date(2015, 1, 1), {"phone": "+7..."}, "pass")
    except ClientNotAdultError as e:
        print(f"Expexted error: {e}")

    anna = Client("Анна Смирнова", date(1990, 5, 15),
                  {"phone": "+7-900-111-22-33", "email": "anna@example.com"}, "anna_pass")
    oleg = Client("Олег Петров", date(1985, 9, 1),
                  {"phone": "+7-900-444-55-66"}, "oleg_pass")
    bank.add_client(anna)
    bank.add_client(oleg)
    print(anna)
    print(oleg, "\n")

    # --- opening account
    print("--- 2. Open accounts ---")
    acc_a1 = bank.open_account(anna.client_id, "savings",
                               balance=10000, currency="RUB",
                               min_balance=1000, interest_rate=0.05)
    acc_a2 = bank.open_account(anna.client_id, "premium",
                               balance=50000, currency="RUB",
                               overdraft_limit=5000, commission=100)
    acc_o1 = bank.open_account(oleg.client_id, "investment",
                               balance=20000, currency="USD")
    print(acc_a1); print(acc_a2); print(acc_o1, "\n")

    # --- authenfication
    print("--- 3. Authenfication ---")
    bank.authenticate_client(anna.client_id, "anna_pass")
    print("Success")


    for i in range(1, 4):
        try:
            bank.authenticate_client(oleg.client_id, "wrong")
        except (AuthenticationError, ClientBlockedError) as e:
            print(f"Attempt {i}: {e}")
    print()

    # --- Operations
    print("--- 4. Operations ---")
    bank.deposit(anna.client_id, "anna_pass", acc_a1.account_id, 500)
    bank.withdraw(anna.client_id, "anna_pass", acc_a1.account_id, 200)
    print(f"Balance acc_a1: {acc_a1.balance}")

    
    try:
        bank.withdraw(anna.client_id, "anna_pass", acc_o1.account_id, 100)
    except InvalidOperationError as e:
        print(f"Expercted error: {e}")
    print(f"Marked with suspicious activity: {anna.suspicious_activity}\n")

   
    print("--- 5. Freeze ---")
    bank.freeze_account(acc_a2.account_id)
    try:
        bank.withdraw(anna.client_id, "anna_pass", acc_a2.account_id, 100)
    except Exception as e:
        print(f"Expected error: {type(e).__name__}: {e}")
    bank.unfreeze_account(acc_a2.account_id)
    print()

   
    print("--- 6. Night time restriction ---")
    night_bank = Bank(now_provider=lambda: datetime(2024, 1, 1, 2, 0))
    night_bank.add_client(anna)
    try:
        night_bank.deposit(anna.client_id, "anna_pass", acc_a1.account_id, 100)
    except RestrictedTimeError as e:
        print(f"Expected error: {e}\n")


    print("--- 7. Analytics ---")
    print(f"Balance Анны:  {bank.get_total_balance(anna.client_id):.2f} RUB")
    print(f"Balance Олега: {bank.get_total_balance(oleg.client_id):.2f} USD")
    print(f"Total in bank: {bank.get_total_balance():.2f}")
    print("Client Rating:")
    for i, (c, total) in enumerate(bank.get_clients_ranking(), 1):
        print(f"  {i}. {c.full_name}: {total:.2f}")
    print()

    print("--- 8. Search ---")
    print(f"Search for'premium': {[a.account_id for a in bank.search_accounts('Анна')]}")
    print(f"Only with active status: {[a.account_id for a in bank.search_accounts(status='active')]}")

#day4
def run_10_transactions_demo():
    
    print("=== СЦЕНАРИЙ: 10 ТРАНЗАКЦИЙ ===\n")

    bank = Bank(now_provider=lambda: datetime(2024, 1, 1, 12, 0))
    converter = currency_converter.CurrencyConverter({("USD", "RUB"): 90.0, ("RUB", "USD"): 0.011})
    queue = TransactionQueue(now_provider=lambda: datetime(2024, 1, 1, 12, 0))
    processor = TransactionProcessor(bank, queue, converter)


    anna = Client("Анна Смирнова", date(1990, 5, 15), {"phone": "+7..."}, "anna_pass")
    oleg = Client("Олег Петров", date(1985, 9, 1), {"phone": "+7..."}, "oleg_pass")
    maria = Client("Мария Иванова", date(1995, 3, 10), {"phone": "+7..."}, "maria_pass")
    bank.add_client(anna); bank.add_client(oleg); bank.add_client(maria)

    
    a_rub   = bank.open_account(anna.client_id, "basic",   balance=10000, currency="RUB")
    a_usd   = bank.open_account(anna.client_id, "savings", balance=500,   currency="USD", min_balance=0)
    a_froz  = bank.open_account(anna.client_id, "basic",   balance=1000,  currency="RUB")
    a_froz.freeze()

    o_rub   = bank.open_account(oleg.client_id, "basic",   balance=5000,  currency="RUB")
    o_prem  = bank.open_account(oleg.client_id, "premium", balance=100,   currency="RUB",
                                 overdraft_limit=500, commission=0)

    m_rub   = bank.open_account(maria.client_id, "basic",  balance=100,   currency="RUB")
    m_closed = bank.open_account(maria.client_id, "basic", balance=0,     currency="RUB")
    m_closed.close()   
    txs = [
        
        bank.create_transfer(a_rub.account_id, o_rub.account_id,
                             amount=1000, currency="RUB", external_rate=0.01),

        
        bank.create_transfer(a_rub.account_id, a_usd.account_id,  # разные валюты, но разные счета того же клиента
                             amount=500, currency="RUB", external_rate=0.01),

        
        bank.create_transfer(a_usd.account_id, o_rub.account_id,
                             amount=100, currency="USD", external_rate=0.0),

      
        Transaction("deposit", 2000, "RUB", to_account_id=a_rub.account_id, commission=0),

        
        Transaction("withdraw", 300, "RUB", from_account_id=o_rub.account_id, commission=10),

        
        bank.create_transfer(m_rub.account_id, o_rub.account_id,
                             amount=500, currency="RUB", external_rate=0.0),

        
        Transaction("transfer", 100, "RUB",
                    from_account_id=a_froz.account_id, to_account_id=o_rub.account_id, commission=0),

        
        Transaction("transfer", 100, "RUB",
                    from_account_id=a_rub.account_id, to_account_id=m_closed.account_id, commission=0),

        
        Transaction("transfer", 400, "RUB",
                    from_account_id=o_prem.account_id, to_account_id=o_rub.account_id, commission=0),

        
        Transaction("deposit", 777, "RUB", to_account_id=m_rub.account_id,
                    commission=0, priority=1),
    ]

    
    for i, tx in enumerate(txs, 1):
        if tx.priority == 5:  # явно не задан
            tx.priority = 5


    for i, tx in enumerate(txs, 1):
        queue.enqueue(tx)
        print(f"  {i:2d}. {tx.type:8s} {tx.amount:>7.2f} {tx.currency} "
              f"priority={tx.priority} id={tx.id}")

    print(f"\nВ очереди: {len(queue)} транзакций\n")

    stats = processor.process_all()
    print(f"\nСтатистика: {stats}\n")


    for acc in [a_rub, a_usd, a_froz, o_rub, o_prem, m_rub, m_closed]:
        print(f"  {acc.owner:18s} {acc.account_id} ({acc.currency}): "
              f"{acc.balance:>10.2f} [{acc.status}]")


    for tx in queue.failed:
        print(f"  {tx.id} {tx.type}: {tx.failure_code} — {tx.failure_reason}")


    completed = [tx for tx in txs if tx.status == "completed"]
    completed.sort(key=lambda t: t.processed_at)
    for tx in completed:
        print(f"  {tx.processed_at:%H:%M:%S} {tx.id} prio={tx.priority} "
              f"{tx.type} {tx.amount} {tx.currency}")


if __name__ == "__main__":
    run_demo()
    run_10_transactions_demo()
 