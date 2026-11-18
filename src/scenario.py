from models import BankAccount, SavingsAccount, PremiumAccount, InvestmentAccount, Bank, Client, Transaction, TransactionQueue, TransactionProcessor, AuditLog, AuditLevel
from utils import (
    ClientNotAdultError, ClientBlockedError, AuthenticationError,
    RestrictedTimeError, AccountNotFoundError, ClientNotAdultError, AccountClosedError,
    AccountFrozenError, InvalidOperationError, InsufficientFundsError, validate_amount
)
from reports import ChartType, ReportBuilder, ReportFormat, ReportType
from collections import defaultdict, Counter
from currency_converter import CurrencyConverter
import json
import logging
from pathlib import Path
from datetime import date, datetime, timedelta
import hashlib 

def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def subsection(title: str) -> None:
    print(f"\n  --- {title} ---")

def _create_infrastructure() -> dict:
    file_path = Path("audit.jsonl")
    file_path.unlink(missing_ok=True)
    now = [datetime(2024, 1, 1, 12, 0)]
    now_provider = lambda: now[0]   
    audit_log = AuditLog(log_file="audit.jsonl", max_entries=5000, now_provider=lambda: now[0])
    bank = Bank(now_provider=lambda: now[0], audit_log=audit_log)
    converter = CurrencyConverter({
        ("USD", "RUB"): 90.0,  ("RUB", "USD"): 0.011,
        ("EUR", "RUB"): 100.0, ("RUB", "EUR"): 0.010,
        ("USD", "EUR"): 0.92,  ("EUR", "USD"): 1.09,
    })
    queue = TransactionQueue(now_provider=now_provider)
    processor = TransactionProcessor(bank, queue, converter)
    print(str(bank.risk_analyzer.thresholds))
    return dict(now=now, now_provider=now_provider,     
                audit_log=audit_log, bank=bank,
                converter=converter, queue=queue, processor=processor)

def _create_clients(bank) -> dict[str, Client]:
    clients = {}
    specs = [
        ("anna",   "Анна Смирнова",       date(1990, 5, 15), "anna_pass"),
        ("oleg",   "Олег Петров",         date(1985, 9, 1),  "oleg_pass"),
        ("maria",  "Мария Смирнова",      date(1995, 3, 10), "maria_pass"),
        ("dmitry", "Дмитрий Иванов",      date(1970, 12, 20),"dmitry_pass"),
        ("elena",  "Елена Фёдорова",      date(2000, 7, 4),  "elena_pass"),
        ("sergei", "Сергей Александров",  date(1988, 3, 22), "sergei_pass"),
        ("irina",  "Ирина Михайлова",     date(1992, 11, 30),"irina_pass"),
    ]
    for key, full_name, birth, password in specs:
        c = Client(full_name, birth, {"phone": "+7-000"}, password)
        bank.add_client(c)
        clients[key] = c
        print(f"  + {c}")
    try:
        Client("Павел Михайлов", date(2015, 3, 25), {}, "p")
    except ClientNotAdultError as e:
        print(f"  [EXPECTED] {type(e).__name__}: {e}")

    return clients

def _create_accounts(bank, clients) -> dict[str, BankAccount]:
    acc = {}
    def _open(key, client_key, acc_type, created_at=None, **kw):
        
        acc[key] = bank.open_account(clients[client_key].client_id, acc_type, **kw)
        
        if created_at is not None:
            acc[key].created_at = created_at
        return acc[key]

    OLD = datetime(2023, 1, 1)
    _open("anna_main", "anna", "basic", created_at=OLD,
          balance=2_000_000, currency="RUB")
    _open("anna_savings", "anna", "savings", balance=100_000, currency="RUB",
          min_balance=1000, interest_rate=0.05)
    _open("anna_usd", "anna", "basic", balance=5_000, currency="USD")
    _open("anna_premium", "anna", "premium", balance=500, currency="RUB",
          overdraft_limit=1000, commission=10)
    _open("oleg_main", "oleg", "basic", created_at=OLD,
          balance=5_000, currency="RUB")
    _open("oleg_savings", "oleg", "savings", balance=500_000, currency="RUB",
          min_balance=5000)
    _open("maria_main", "maria", "basic", created_at=OLD,
          balance=50, currency="RUB")
    _open("maria_new", "maria", "basic", balance=0, currency="RUB")
    _open("maria_new_2", "maria", "basic", balance=0, currency="RUB")
    _open("dmitry_eur", "dmitry", "basic", balance=3_000, currency="EUR")
    _open("dmitry_main", "dmitry", "basic", balance=20_000, currency="RUB")
    _open("elena_main", "elena", "basic", balance=1_000, currency="RUB")
    _open("sergey_main", "sergei", "basic", balance=500, currency="RUB")
    _open("irina_premium", "irina", "premium", balance=200, currency="RUB",
          overdraft_limit=1000, commission=10)
    _open("irina_frozen", "irina", "basic", balance=500, currency="RUB")
    bank.freeze_account(acc["irina_frozen"].account_id) 
    _open("irina_block", "irina", "basic", balance=0, currency="RUB")
    bank.close_account(acc["irina_block"].account_id) 
    for name, a in acc.items():
        tag = ""
        if a.status == "frozen":
            tag = " [FROZEN]"
        elif a.status == "closed":
            tag = " [CLOSED]"
        elif (bank._now() - a.created_at).days < 30:
            tag = " [NEW]"
        print(f"  {name:14s}: {a}{tag}")

    return acc
def _build_transactions(bank, accounts) -> list[Transaction]:

    txs: list[Transaction] = []
    nowp = bank._now

    def T(tx_id, **kw):
        """Прямая Transaction (deposit / withdraw)."""
        return Transaction(transaction_id=tx_id, now_provider=nowp, **kw)

    def TT(tx_id, **kw):
        """Transfer через bank (считает комиссию по external_rate)."""
        return bank.create_transfer(transaction_id=tx_id, **kw)

    # 1-2. Внешние RUB-переводы Anna → Oleg (комиссия 1%)
    txs.append(TT("tx01", from_id=accounts["anna_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=1000, currency="RUB", external_rate=0.01))
    txs.append(TT("tx02", from_id=accounts["anna_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=500, currency="RUB", external_rate=0.01))

    # 3. Внутренний Anna → Anna_savings (комиссия 0)
    txs.append(TT("tx03", from_id=accounts["anna_main"].account_id,
                  to_id=accounts["anna_savings"].account_id,
                  amount=500, currency="RUB", external_rate=0.01))

    # 4. Конверсия USD → RUB (100 × 90 = 9000 RUB)
    txs.append(TT("tx04", from_id=accounts["anna_usd"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=100, currency="USD", external_rate=0.0))

    # 5. Конверсия EUR → RUB (100 × 100 = 10000 RUB)
    txs.append(TT("tx05", from_id=accounts["dmitry_eur"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=100, currency="EUR", external_rate=0.0))

    # 6-7. Депозиты
    txs.append(T("tx06", transaction_type="deposit",
                 amount=500, currency="RUB",
                 to_account_id=accounts["oleg_main"].account_id))
    txs.append(T("tx07", transaction_type="deposit",
                 amount=1000, currency="RUB",
                 to_account_id=accounts["elena_main"].account_id))

    # 8-9. Снятия с комиссией
    txs.append(T("tx08", transaction_type="withdraw",
                 amount=300, currency="RUB",
                 from_account_id=accounts["oleg_main"].account_id,
                 commission=10))
    txs.append(T("tx09", transaction_type="withdraw",
                 amount=500, currency="RUB",
                 from_account_id=accounts["dmitry_main"].account_id,
                 commission=5))

    # 10. Premium-перевод
    txs.append(TT("tx10", from_id=accounts["anna_premium"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=500, currency="RUB", external_rate=0.0))

    # 11. Premium уходит в овердрафт (200 − 800 = −600 ≥ −1000)
    txs.append(TT("tx11", from_id=accounts["irina_premium"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=800, currency="RUB", external_rate=0.0))

    # 12-15. Мария накапливает историю для «frequent»
    txs.append(T("tx12", transaction_type="deposit",
                 amount=50000, currency="RUB",
                 to_account_id=accounts["maria_main"].account_id))
    txs.append(TT("tx13", from_id=accounts["maria_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=1000, currency="RUB", external_rate=0.0))
    txs.append(TT("tx14", from_id=accounts["maria_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=1000, currency="RUB", external_rate=0.0))
    txs.append(TT("tx15", from_id=accounts["maria_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=1000, currency="RUB", external_rate=0.0))

    # 16-17. Large (MEDIUM — проходят)
    txs.append(TT("tx16", from_id=accounts["anna_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=150_000, currency="RUB", external_rate=0.01))
    txs.append(TT("tx17", from_id=accounts["anna_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=200_000, currency="RUB", external_rate=0.01))

    # 18-20. Frequent (Мария уже имеет 4 completed — пятая = флаг)
    txs.append(TT("tx18", from_id=accounts["maria_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=1000, currency="RUB", external_rate=0.0))
    txs.append(TT("tx19", from_id=accounts["maria_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=1000, currency="RUB", external_rate=0.0))
    txs.append(TT("tx20", from_id=accounts["maria_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=1000, currency="RUB", external_rate=0.0))

    # 21-22. New account (MEDIUM — проходят)
    txs.append(TT("tx21", from_id=accounts["anna_main"].account_id,
                  to_id=accounts["maria_new"].account_id,
                  amount=500, currency="RUB", external_rate=0.0))
    txs.append(TT("tx22", from_id=accounts["anna_main"].account_id,
                  to_id=accounts["maria_new_2"].account_id,
                  amount=500, currency="RUB", external_rate=0.0))

    # 23. HIGH: large + frequent + new → BLOCKED
    txs.append(TT("tx23", from_id=accounts["anna_main"].account_id,
                  to_id=accounts["maria_new"].account_id,
                  amount=150_000, currency="RUB", external_rate=0.0))

    # 24. Large + frequent = MEDIUM (проходит)
    txs.append(TT("tx24", from_id=accounts["anna_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=300_000, currency="RUB", external_rate=0.0))

    # 25. Night + new = MEDIUM (scheduled_at=23:00)
    txs.append(TT("tx25", from_id=accounts["anna_main"].account_id,
                  to_id=accounts["maria_new_2"].account_id,
                  amount=500, currency="RUB", external_rate=0.0,
                  scheduled_at=datetime(2024, 1, 1, 23, 0)))

    # 26.  HIGH: large + night + new + frequent → BLOCKED
    txs.append(TT("tx26", from_id=accounts["anna_main"].account_id,
                  to_id=accounts["maria_new"].account_id,
                  amount=300_000, currency="RUB", external_rate=0.0,
                  scheduled_at=datetime(2024, 1, 2, 3, 0)))

    # 27-28. New account (MEDIUM)
    txs.append(TT("tx27", from_id=accounts["oleg_main"].account_id,
                  to_id=accounts["maria_new"].account_id,
                  amount=100, currency="RUB", external_rate=0.0))
    txs.append(TT("tx28", from_id=accounts["dmitry_main"].account_id,
                  to_id=accounts["maria_new_2"].account_id,
                  amount=100, currency="RUB", external_rate=0.0))

    # 29. Night = MEDIUM
    txs.append(TT("tx29", from_id=accounts["anna_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=1000, currency="RUB", external_rate=0.0,
                  scheduled_at=datetime(2024, 1, 1, 23, 30)))

    # 30. Large + frequent = MEDIUM
    txs.append(TT("tx30", from_id=accounts["anna_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=500_000, currency="RUB", external_rate=0.01))

    # 31. insufficient_funds: Мария ~44k, перевод 100k
    txs.append(TT("tx31", from_id=accounts["maria_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=100_000, currency="RUB", external_rate=0.0))

    # 32. insufficient_funds: anna_savings ~100k, перевод 200k
    txs.append(TT("tx32", from_id=accounts["anna_savings"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=200_000, currency="RUB", external_rate=0.0))

    # 33. account_frozen (получатель заморожен)
    txs.append(TT("tx33", from_id=accounts["anna_main"].account_id,
                  to_id=accounts["irina_frozen"].account_id,
                  amount=500, currency="RUB", external_rate=0.0))

    # 34. account_closed (получатель закрыт)
    txs.append(T("tx34", transaction_type="transfer",
             amount=500, currency="RUB",
             from_account_id=accounts["anna_main"].account_id,
             to_account_id=accounts["irina_block"].account_id,
             commission=0))

    # 35. insufficient_funds: maria_new пуст
    txs.append(T("tx35", transaction_type="withdraw",
                 amount=100, currency="RUB",
                 from_account_id=accounts["maria_new"].account_id,
                 commission=0))

    # 36. insufficient_funds: premium overdraft превышен
    #     anna_premium после tx10: 0, overdraft=1000 → доступно 1000 < 2000
    txs.append(TT("tx36", from_id=accounts["anna_premium"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=2000, currency="RUB", external_rate=0.0))

    # 37. insufficient_funds: elena ~2000, перевод 5000
    txs.append(TT("tx37", from_id=accounts["elena_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=5000, currency="RUB", external_rate=0.0))

    # 38. insufficient_funds: dmitry_eur ~2900, перевод 5000
    txs.append(TT("tx38", from_id=accounts["dmitry_eur"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=5000, currency="EUR", external_rate=0.0))

    # 39. insufficient_funds: sergey 500, перевод 1000
    txs.append(TT("tx39", from_id=accounts["sergey_main"].account_id,
                  to_id=accounts["oleg_main"].account_id,
                  amount=1000, currency="RUB", external_rate=0.0))

    # 40. account_frozen (получатель заморожен)
    txs.append(TT("tx40", from_id=accounts["oleg_main"].account_id,
                  to_id=accounts["irina_frozen"].account_id,
                  amount=500, currency="RUB", external_rate=0.0))

    return txs

def _simulate(processor, queue, txs, now) -> None:
    

    
    subsection("Стадия 1. Попадание в очередь")
    for tx in txs:
        queue.enqueue(tx)

    print(f"  Всего в очереди:       {len(queue)}")
    scheduled = [tx for tx in txs if tx.scheduled_at and tx.scheduled_at > now[0]]
    print(f"  Отложенных (scheduled): {len(scheduled)}")
    for tx in scheduled:
        print(f"    {tx.id} → запланирована на {tx.scheduled_at}")

    
    subsection("Стадия 2. Исполнение (поэтапно)")

    phases = [
        ("ДЕНЬ (12:00)", datetime(2024, 1, 1, 12, 0)),
        ("ВЕЧЕР (23:00)", datetime(2024, 1, 1, 23, 0)),
        ("НОЧЬ (03:00)", datetime(2024, 1, 2, 3, 0)),
    ]
    for label, ts in phases:
        now[0] = ts
        print(f"\n  [Время: {ts:%Y-%m-%d %H:%M}]")
        n = 0
        while True:
            tx = queue.dequeue()
            if tx is None:
                break
            processor._process_transaction(tx)
            
            tail = f" — {tx.failure_code}" if tx.failure_code else ""
            print(f"    {tx.id:6s} {tx.type:8s} {tx.amount:>10.2f} "
                  f"{tx.currency:3s} | {tx.status:9s}{tail}")
            n += 1
        if n == 0:
            print("    (нет готовых к обработке)")

    
    now[0] = datetime(2024, 1, 1, 12, 0)

 
    subsection("Стадия 3. Отклонение")

    print(f"\n  Dead-letter (queue.failed): {len(queue.failed)}")
    for tx in queue.failed:
        print(f"    {tx.id:6s} {tx.type:8s} | {tx.failure_code:20s} "
              f"| attempts={tx.attempts} | {tx.failure_reason}")

    audit = processor.bank.audit_log
    print("\n  Audit ERROR (последние 15, новые первыми):")
    for e in audit.get_entries(level=AuditLevel.ERROR, limit=15, reverse=True):
        print(f"    [{e.timestamp:%H:%M}] {e.event_type}: {e.message[:70]}")

    print("\n  Заблокировано по риску (CRITICAL):")
    for e in audit.get_entries(event_type="risk_blocked"):
        print(f"    [{e.timestamp:%H:%M}] tx={e.transaction_id} "
              f"reasons={e.metadata.get('reasons')}")

    print("\n  Retry (WARNING):")
    retries = audit.get_entries(event_type="transaction_retry")
    print(f"    всего попыток retry: {len(retries)}")
    if retries:
        for e in retries[:5]:
            print(f"      [{e.timestamp:%H:%M}] tx={e.transaction_id} "
                  f"attempt={e.metadata.get('attempt')}")



def _show_user_scenarios(bank, audit_log, client: Client) -> None:
    section(f"ПОЛЬЗОВАТЕЛЬСКИЙ СЦЕНАРИЙ: {client.full_name}")

   
    subsection("Счета")
    if not client.account_ids:
        print("  (нет открытых счетов)")
    else:
        for aid in client.account_ids:
            acc = bank.accounts.get(aid)
            if acc is None:
                continue
            tag = ""
            if acc.status == "frozen":
                tag = " [FROZEN]"
            elif acc.status == "closed":
                tag = " [CLOSED]"
            elif (bank._now() - acc.created_at).days < 30:
                tag = " [NEW]"
            print(f"  {acc}{tag}")
        totals = bank.get_total_balance(client.client_id)
        breakdown = ", ".join(f"{v:,.2f} {c}" for c, v in sorted(totals.items())) or "—"
        print(f"\n  Суммарный баланс: {breakdown}")

   
    subsection("История (audit_log, последние 10)")
    entries = audit_log.get_entries(client_id=client.client_id, limit=10, reverse=True)
    if not entries:
        print("  (нет записей)")
    else:
        for e in entries:
            print(f"  [{e.timestamp:%H:%M}] {e.level.name:8s} {e.event_type}: {e.message[:70]}")

    subsection("История (activity_log клиента)")
    if not client.activity_log:
        print("  (пусто)")
    else:
        for line in client.activity_log[-10:]:
            print(f"  {line}")

    
    subsection("Риск-профиль")
    try:
        profile = bank.report_client_risk_profile(client.client_id)
        print(json.dumps(profile, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(f"  [WARN] {type(exc).__name__}: {exc}")


def _balance_by_currency(bank) -> dict[str, dict]:
    """Сгруппировать балансы по валютам: {RUB: {total, count}, ...}."""
    result: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0})
    for acc in bank.accounts.values():
        if acc.status == "closed":
            continue
        result[acc.currency]["total"] += acc.balance
        result[acc.currency]["count"] += 1
    return dict(result)


def _show_reports(bank, txs, queue) -> None:
    section("ОТЧЁТЫ")

    
    subsection("Топ-3 клиентов по суммарному балансу (мультивалютный)")
    ranking = bank.get_clients_ranking()

    for i, (client, totals) in enumerate(ranking[:3], 1):
        # totals — уже dict {"RUB": X, "USD": Y}, не число
        breakdown = ", ".join(
            f"{v:,.2f} {c}" for c, v in sorted(totals.items())
        ) or "—"
        print(f"  {i}. {client.full_name:25s} — {breakdown}")
    
    subsection("Статистика транзакций")
    completed = [tx for tx in txs if tx.status == "completed"]
    failed = [tx for tx in txs if tx.status == "failed"]
    cancelled = [tx for tx in txs if tx.status == "cancelled"]
    other = [tx for tx in txs if tx.status not in
             {"completed", "failed", "cancelled"}]
    total = len(txs)
    pct = lambda n: f"({n / total * 100:.1f}%)" if total else "(0%)"

    print(f"  Всего:         {total}")
    print(f"  Успешных:      {len(completed):3d} {pct(len(completed))}")
    print(f"  Отклонённых:   {len(failed):3d} {pct(len(failed))}")
    print(f"  Отменённых:    {len(cancelled):3d} {pct(len(cancelled))}")
    if other:
        print(f"  В процессе:    {len(other):3d} {pct(len(other))} ← ОШИБКА, не должно быть")

    by_type = Counter(tx.type for tx in txs)
    print(f"\n  По типам:      " + ", ".join(f"{k}={v}" for k, v in by_type.items()))

    by_code = Counter(tx.failure_code for tx in failed if tx.failure_code)
    if by_code:
        print(f"  По ошибкам:    " + ", ".join(f"{k}={v}" for k, v in by_code.most_common()))

    if failed:
        avg_attempts = sum(tx.attempts for tx in failed) / len(failed)
        print(f"  Средние попытки для failed: {avg_attempts:.2f}")

    print(f"  Dead-letter:   {len(queue.failed)} (должно совпадать с отклонёнными)")

  
    subsection("Общий баланс банка (по валютам)")
    by_ccy = _balance_by_currency(bank)
    for ccy in sorted(by_ccy):
        info = by_ccy[ccy]
        print(f"  {ccy}: {info['total']:>15.2f} ({info['count']} счетов)")

    # --- Бонус: JSON-отчёты аудита ---
    subsection("Отчёт: подозрительные операции")
    print(json.dumps(bank.report_suspicious_operations(), indent=2, ensure_ascii=False))

    subsection("Отчёт: статистика ошибок")
    print(json.dumps(bank.report_error_statistics(), indent=2, ensure_ascii=False))


def _run_self_checks(bank, queue, audit_log, txs, accounts) -> None:
    section("SELF-CHECKS (инварианты)")

    completed = [tx for tx in txs if tx.status == "completed"]
    failed = [tx for tx in txs if tx.status == "failed"]
    risk_blocked = [tx for tx in txs if tx.failure_code == "risk_blocked"]
    in_flight = [tx for tx in txs if tx.status not in
                 {"completed", "failed", "cancelled"}]

    checks = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        status = "OK " if condition else "FAIL"
        print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
        checks.append(condition)

    check("В очереди не осталось 'зависших' транзакций",
          len(in_flight) == 0, f"in_flight={len(in_flight)}")

    check("AuditLog содержит >= 90 записей",
          len(audit_log) >= 90, f"получено {len(audit_log)}")

    check("Есть >= 2 CRITICAL (риск-блокировки)",
          audit_log.count_by_level()[AuditLevel.CRITICAL] >= 2,
          f"получено {audit_log.count_by_level()[AuditLevel.CRITICAL]}")

    check("Есть >= 2 заблокированных по риску",
          len(risk_blocked) >= 2, f"получено {len(risk_blocked)}")

    check("Успешных >= 20",
          len(completed) >= 20, f"получено {len(completed)}")

    check("Dead-letter == отклонённые",
          len(queue.failed) == len(failed),
          f"dead={len(queue.failed)} failed={len(failed)}")

    check("Все failed имеют failure_code",
          all(tx.failure_code for tx in failed),
          f"без кода: {[tx.id for tx in failed if not tx.failure_code]}")

    
    completed_events = audit_log.count_by_event_type().get("transaction_completed", 0)
    check("Audit: transaction_completed == completed",
          completed_events == len(completed),
          f"audit={completed_events} txs={len(completed)}")

   
    check("Замороженный счёт irina_frozen не изменился",
          accounts["irina_frozen"].balance == 500,
          f"balance={accounts['irina_frozen'].balance}")

    
    check("Закрытый счёт irina_block не изменился",
          accounts["irina_block"].balance == 0,
          f"balance={accounts['irina_block'].balance}")

   
    check("maria_new баланс не отрицательный",
          accounts["maria_new"].balance >= 0,
          f"balance={accounts['maria_new'].balance}")

    print(f"\n  Итого: {sum(checks)}/{len(checks)} проверок пройдено")
    assert all(checks), f"Провалено {len(checks) - sum(checks)} инвариантов"


def _demo_reports(infra: dict, clients: dict, txs: list) -> None:


    section("10. ОТЧЁТЫ (ReportBuilder)")

    builder = ReportBuilder(
        bank=infra["bank"],
        audit_log=infra["audit_log"],
        output_dir="reports",
        now_provider=infra["now_provider"],
    )



    print(builder.render_text(ReportType.BANK))
    print()
    print(builder.render_text(ReportType.RISK))
    print()

    anna_result = builder.build_report(
        ReportType.CLIENT,
        client_id=clients["anna"].client_id,
        formats=[ReportFormat.TEXT, ReportFormat.JSON, ReportFormat.CSV],
        charts=[ChartType.PIE, ChartType.BAR, ChartType.BALANCE_FLOW],
        transactions=txs,
    )
    print(f"\n  Анна: {anna_result['text'][:300]}...")
    print(f"\n  Файлы Анны:")
    for p in anna_result["files"]:
        print(f"    📄 {p}")
    for p in anna_result["charts"]:
        print(f"    📊 {p}")

    for rtype in (ReportType.BANK, ReportType.RISK):
        res = builder.build_report(
            rtype,
            formats=[ReportFormat.JSON, ReportFormat.CSV],
            charts=[ChartType.PIE, ChartType.BAR],
        )
        print(f"\n  {rtype.value}:")
        for p in res["files"]:
            print(f"    📄 {p}")
        for p in res["charts"]:
            print(f"    📊 {p}")


def run_full_scenario() -> None:
    section("1. ИНИЦИАЛИЗАЦИЯ")
    infra = _create_infrastructure()
    print(f"  Bank:      {infra['bank']}")
    print(f"  AuditLog:  entries={len(infra['audit_log'])}")
    print(f"  Риск-пороги: {infra['bank'].risk_analyzer.thresholds}")

    section("2. КЛИЕНТЫ")
    clients = _create_clients(infra["bank"])

    section("3. СЧЕТА")
    accounts = _create_accounts(infra["bank"], clients)

    section("4. ТРАНЗАКЦИИ — ПОДГОТОВКА (40 шт.)")
    txs = _build_transactions(infra["bank"], accounts)
    print(f"  Создано транзакций: {len(txs)}")
    print(f"    transfer: {sum(1 for t in txs if t.type == 'transfer')}")
    print(f"    deposit:  {sum(1 for t in txs if t.type == 'deposit')}")
    print(f"    withdraw: {sum(1 for t in txs if t.type == 'withdraw')}")
    print(f"  Отложенных (scheduled_at в будущем): "
          f"{sum(1 for t in txs if t.scheduled_at)}")

    section("5. СИМУЛЯЦИЯ")
    _simulate(infra["processor"], infra["queue"], txs, infra["now"])

    section("6. ПОЛЬЗОВАТЕЛЬСКИЕ СЦЕНАРИИ")
    _show_user_scenarios(infra["bank"], infra["audit_log"], clients["anna"])
    _show_user_scenarios(infra["bank"], infra["audit_log"], clients["maria"])
    _show_user_scenarios(infra["bank"], infra["audit_log"], clients["sergei"])

    section("7. ОТЧЁТЫ")
    _show_reports(infra["bank"], txs, infra["queue"])

    section("8. ФАЙЛ АУДИТА")
    log_path = Path("audit.jsonl")
    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8").splitlines()
        print(f"  Файл: {log_path} | строк: {len(lines)}")
        if lines:
            print(f"  Первая:    {lines[0][:110]}...")
            print(f"  Последняя: {lines[-1][:110]}...")

    section("9. SELF-CHECKS")
    _run_self_checks(infra["bank"], infra["queue"], infra["audit_log"],
                     txs, accounts)

    print("\n" + "=" * 72)
    print("  ✅ СЦЕНАРИЙ ЗАВЕРШЁН УСПЕШНО")
    print("=" * 72)

    _demo_reports(infra, clients, txs)

    print("\n" + "=" * 72)
    print("  ✅ СЦЕНАРИЙ ЗАВЕРШЁН УСПЕШНО")
    print("=" * 72)

if __name__ == "__main__":
    run_full_scenario()
        