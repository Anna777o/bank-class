from models import BankAccount, SavingsAccount, PremiumAccount, InvestmentAccount, Bank, Client, Transaction, TransactionQueue, TransactionProcessor, AuditLog, AuditLevel
from utils import (
    ClientNotAdultError, ClientBlockedError, AuthenticationError,
    RestrictedTimeError, AccountNotFoundError, ClientNotAdultError, AccountClosedError,
    AccountFrozenError, InvalidOperationError, InsufficientFundsError, validate_amount
)
from currency_converter import CurrencyConverter
import json
import logging
from pathlib import Path
from datetime import date, datetime, timedelta
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
    converter = CurrencyConverter({("USD", "RUB"): 90.0, ("RUB", "USD"): 0.011})
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

def section(title: str) -> None:
    print("\n" + "=" * 68)
    print(f"  {title}")
    print("=" * 68)


def print_tx_result(tx: Transaction, audit_log: AuditLog) -> None:
    """Краткая строка по итогу транзакции + причины риска из audit."""
    alerts = audit_log.get_entries(event_type="risk_alert", transaction_id=tx.id)
    blocked = audit_log.get_entries(event_type="risk_blocked", transaction_id=tx.id)
    reasons: list[str] = []
    for e in alerts + blocked:
        reasons.extend(e.metadata.get("reasons", []))
    tail = f" | risk: {reasons}" if reasons else ""
    print(f"  {tx.id:16s} | {tx.status:9s} | {tx.failure_code or '-':18s}{tail}")


# ---------- Демонстрация ----------
def demo_main() -> None:
    # Чистим файл аудита от прошлых запусков
    log_path = Path("audit.jsonl")
    if log_path.exists():
        log_path.unlink()

    # ============================================================
    section("1. ИНФРАСТРУКТУРА")
    # ============================================================
    now = lambda: datetime(2024, 1, 1, 12, 0)

    audit_log = AuditLog(log_file=log_path, max_entries=2000, now_provider=now)
    bank = Bank(now_provider=now, audit_log=audit_log)   # RiskAnalyzer создастся сам
    converter = CurrencyConverter({("USD", "RUB"): 90.0, ("RUB", "USD"): 0.011})
    queue = TransactionQueue(now_provider=now)
    processor = TransactionProcessor(bank, queue, converter)

    print(f"  AuditLog:  {audit_log}")
    print(f"  Bank:      {bank}")
    print(f"  RiskAnalyzer thresholds: {bank.risk_analyzer.thresholds}")

    # ============================================================
    section("2. КЛИЕНТЫ")
    # ============================================================
    anna = Client("Анна Смирнова", date(1990, 5, 15), {"phone": "+7-111"}, "anna_pass")
    oleg = Client("Олег Петров", date(1985, 9, 1), {"phone": "+7-222"}, "oleg_pass")
    maria = Client("Мария Иванова", date(1995, 3, 10), {"phone": "+7-333"}, "maria_pass")

    for c in (anna, oleg, maria):
        bank.add_client(c)
        print(f"  + {c}")

    # Проверка возраста
    try:
        Client("Ребёнок", date.today() - timedelta(days=365 * 10), {}, "pass")
    except ClientNotAdultError as e:
        print(f"  [EXPECTED] {type(e).__name__}: {e}")

    # ============================================================
    section("3. СЧЕТА")
    # ============================================================
    anna_basic = bank.open_account(anna.client_id, "basic", balance=500_000, currency="RUB")
    anna_usd = bank.open_account(anna.client_id, "savings", balance=5_000, currency="USD", min_balance=0)
    anna_premium = bank.open_account(
        anna.client_id, "premium", balance=500, currency="RUB",
        overdraft_limit=1000, commission=10,
    )

    oleg_basic = bank.open_account(oleg.client_id, "basic", balance=5_000, currency="RUB")
    oleg_basic.created_at = datetime(2023, 1, 1, 12, 0)        # «старый» счёт

    maria_basic = bank.open_account(maria.client_id, "basic", balance=100, currency="RUB")
    maria_basic.created_at = datetime(2023, 6, 1, 12, 0)       # «старый» счёт

    maria_new = bank.open_account(maria.client_id, "basic", balance=0, currency="RUB")
    # created_at = 12:00 сегодня → «новый» счёт → попадёт под правило

    frozen = bank.open_account(anna.client_id, "basic", balance=1_000, currency="RUB")
    frozen.created_at = datetime(2023, 1, 1, 12, 0)
    bank.freeze_account(frozen.account_id)

    for acc in (anna_basic, anna_usd, anna_premium, oleg_basic,
                maria_basic, maria_new, frozen):
        print(f"  {acc}")

    # ============================================================
    section("4. ОБЫЧНЫЕ ОПЕРАЦИИ — копим историю для правила «частота»")
    # ============================================================
    for i in range(1, 7):
        tx = bank.create_transfer(
            anna_basic.account_id, oleg_basic.account_id,
            amount=1_000, currency="RUB",
            external_rate=0.01,
            transaction_id=f"tx{i:02d}",
        )
        queue.enqueue(tx)
        processor.process_one()
        print_tx_result(tx, audit_log)

    # ============================================================
    section("5. РИСКОВЫЕ ОПЕРАЦИИ")
    # ============================================================
    # MEDIUM: крупная + частая → пройдёт
    tx_large = bank.create_transfer(
        anna_basic.account_id, oleg_basic.account_id,
        amount=150_000, currency="RUB", transaction_id="tx_large",
    )
    queue.enqueue(tx_large)
    processor.process_one()
    print_tx_result(tx_large, audit_log)

    # HIGH: крупная + частая + НОВЫЙ счёт → блокировка
    tx_high = bank.create_transfer(
        anna_basic.account_id, maria_new.account_id,
        amount=200_000, currency="RUB", transaction_id="tx_high",
    )
    queue.enqueue(tx_high)
    processor.process_one()
    print_tx_result(tx_high, audit_log)

    # ============================================================
    section("6. ОШИБОЧНЫЕ ОПЕРАЦИИ")
    # ============================================================
    # Нехватка средств
    tx_insufficient = bank.create_transfer(
        maria_basic.account_id, oleg_basic.account_id,
        amount=500, currency="RUB", transaction_id="tx_insufficient",
    )
    queue.enqueue(tx_insufficient)
    processor.process_one()
    print_tx_result(tx_insufficient, audit_log)

    # Замороженный счёт → retry → failed
    tx_frozen = bank.create_transfer(
        frozen.account_id, oleg_basic.account_id,
        amount=100, currency="RUB",
        transaction_id="tx_frozen", max_attempts=3,
    )
    queue.enqueue(tx_frozen)
    for _ in range(3):
        processor.process_one()
    print_tx_result(tx_frozen, audit_log)
    print(f"    attempts={tx_frozen.attempts}")

    # Конвертация USD → RUB
    tx_conv = bank.create_transfer(
        anna_usd.account_id, oleg_basic.account_id,
        amount=500, currency="USD",
        external_rate=0.0,
        transaction_id="tx_conv",
    )
    queue.enqueue(tx_conv)
    processor.process_one()
    print_tx_result(tx_conv, audit_log)

    # Premium уходит в овердрафт
    tx_premium = bank.create_transfer(
        anna_premium.account_id, oleg_basic.account_id,
        amount=500, currency="RUB", transaction_id="tx_premium",
    )
    queue.enqueue(tx_premium)
    processor.process_one()
    print_tx_result(tx_premium, audit_log)

    # ============================================================
    section("7. ИТОГОВЫЕ БАЛАНСЫ")
    # ============================================================
    for acc in (anna_basic, anna_usd, anna_premium, oleg_basic,
                maria_basic, maria_new, frozen):
        print(f"  {acc}")

    # Проверки-инварианты (падаем, если что-то не так)
    assert anna_basic.balance == 342_440, f"Anna basic: {anna_basic.balance}"
    assert maria_new.balance == 0, "Maria new: blocked tx not deducted"
    assert oleg_basic.balance == 206_500, f"Oleg basic: {oleg_basic.balance}"
    assert anna_premium.balance == -5, f"Anna premium: {anna_premium.balance}"
    assert frozen.balance == 1_000, "Frozen unchanged"
    print("\n  [OK] Все инварианты балансов сошлись")

    # ============================================================
    section("8. ФИЛЬТРАЦИЯ AUDITLOG")
    # ============================================================
    print(f"  Всего записей: {len(audit_log)}")
    print(f"  По уровням:    {audit_log.count_by_level()}")
    print(f"  По типам:      {audit_log.count_by_event_type()}")

    print("\n  5 последних предупреждений (новые первыми):")
    for e in audit_log.get_entries(level=AuditLevel.WARNING, limit=5, reverse=True):
        print(f"    {e}")

    print("\n  Заблокированные операции:")
    for e in audit_log.get_entries(event_type="risk_blocked"):
        print(f"    {e}")

    print("\n  Анна — последние 5 записей:")
    for e in audit_log.get_entries(client_id=anna.client_id, limit=5, reverse=True):
        print(f"    {e}")

    # ============================================================
    section("9. ОТЧЁТЫ АУДИТА")
    # ============================================================
    print("\n  Подозрительные операции:")
    print(json.dumps(bank.report_suspicious_operations(), indent=2, ensure_ascii=False))

    print("\n  Риск-профиль Анны:")
    print(json.dumps(bank.report_client_risk_profile(anna.client_id),
                     indent=2, ensure_ascii=False))

    print("\n  Статистика ошибок:")
    print(json.dumps(bank.report_error_statistics(), indent=2, ensure_ascii=False))

    # ============================================================
    section("10. ФАЙЛ АУДИТА (JSONL)")
    # ============================================================
    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8").splitlines()
        print(f"  Файл: {log_path} | строк: {len(lines)}")
        if lines:
            print(f"  Первая: {lines[0][:120]}...")
            print(f"  Последняя: {lines[-1][:120]}...")

    # ============================================================
    section("11. НОЧНОЙ РИСК (23:00 — Bank разрешает, Risk флагует)")
    # ============================================================
    demo_night()

    # ============================================================
    section("12. ОГРАНИЧЕНИЕ ПО ВРЕМЕНИ (02:00 — Bank блокирует)")
   
    demo_time_restriction()


def demo_night() -> None:
    """23:00: Bank.RESTRICTED_HOURS=(0,5) разрешает, RiskAnalyzer.night_hours=(22,6) флагует."""
    now = lambda: datetime(2024, 1, 1, 23, 0)
    audit = AuditLog(now_provider=now)
    bank = Bank(now_provider=now, audit_log=audit)
    converter = CurrencyConverter({("USD", "RUB"): 90.0})
    queue = TransactionQueue(now_provider=now)
    processor = TransactionProcessor(bank, queue, converter)

    anna = Client("Анна", date(1990, 5, 15), {}, "p")
    oleg = Client("Олег", date(1985, 9, 1), {}, "p")
    bank.add_client(anna)
    bank.add_client(oleg)

    a = bank.open_account(anna.client_id, "basic", balance=10_000, currency="RUB")
    o = bank.open_account(oleg.client_id, "basic", balance=0, currency="RUB")
    o.created_at = datetime(2023, 1, 1, 12, 0)

    tx = bank.create_transfer(a.account_id, o.account_id,
                              amount=500, currency="RUB", transaction_id="night_tx")
    queue.enqueue(tx)
    processor.process_one()

    print(f"  {tx.id}: status={tx.status}")
    for e in audit.get_entries(event_type="risk_alert"):
        print(f"  risk_alert: {e.metadata.get('reasons')}")


def demo_time_restriction() -> None:
    """02:00: Bank.RESTRICTED_HOURS=(0,5) блокирует операцию до риск-анализа."""
    # Мутабельное «сейчас»: открываем счёт днём, потом переводим часы на ночь
    now = [datetime(2024, 1, 1, 12, 0)]
    now_provider = lambda: now[0]

    audit = AuditLog(now_provider=now_provider)
    bank = Bank(now_provider=now_provider, audit_log=audit)

    anna = Client("Анна", date(1990, 5, 15), {}, "p")
    bank.add_client(anna)
    acc = bank.open_account(anna.client_id, "basic", balance=10_000, currency="RUB")

    # Переводим «сейчас» на 02:00 — попадает в RESTRICTED_HOURS
    now[0] = datetime(2024, 1, 1, 2, 0)

    try:
        bank.deposit(anna.client_id, "p", acc.account_id, 500)
    except RestrictedTimeError as e:
        print(f"  [EXPECTED] {type(e).__name__}: {e}")


if __name__ == "__main__":
    run_demo()
    run_10_transactions_demo()
    demo_main()
 