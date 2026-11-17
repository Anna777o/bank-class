# Описание алгоритма
## 1. Счета
- `SavingsAccount`: `withdraw` → `InvalidOperationError`, если `balance - amount < min_balance`.
- `PremiumAccount`: `can_send(amount)` → `amount <= balance + overdraft_limit`. Списывает `amount + commission`.
- `InvestmentAccount`: `invest(asset, amount)` из свободного баланса; `project_yearly_growth(rates)`.

`_balance` меняется только внутри класса. Снаружи — read-only `account.balance`.

## 2. Транзакции

| Тип | Формула |
|---|---|
| `deposit` | `dst += amount` |
| `withdraw` | `src -= amount + commission` |
| `transfer` | `src -= debit`, `dst += converted` |

**State machine:** `pending → processing → completed` / `failed`. Из `pending` — `cancel() → cancelled`. Из `processing` — `mark_pending_for_retry()` (если `attempts < max`).

`_require_status(expected)` в каждом `mark_*`. `failure_reason is not None ⟺ failed`. `total_debit = amount + commission`.

**Queue:** 2 кучи — `_pending` (`heapq[(priority, seq, tx)]`, `priority=1` первым) + `_scheduled`. `dequeue()` → `_promote_ready()` → `heappop`. Ленивая отмена (cancel ставит статус, `dequeue` пропускает). `__len__` — только `_pending` без cancelled.

⚠️ **Обработка:** `while True: tx = dequeue(); if tx is None: break`. Не `while queue:` — отложенные не обработаются.

## 3. `TransactionProcessor`
tx.mark_processing()

try:
if risk_check: bank.analyze_transaction_risk(tx) # может raise Suspicious
_dispatch(tx)
tx.mark_completed()
audit_log.info("transaction_completed", ..., client_id=...)
except Exception as exc: _handle_error(tx, exc, client_id)


⚠️ `analyze_transaction_risk` — **внутри** общего `try` (иначе «зомби» в `processing`).
⚠️ `client_id` через `account_owners.get(from) or .get(to)` — иначе `_check_frequency` не работает.

**Атомарность (фазы):**
- Фаза 1: `_get_active_account(src, dst)` + `src.can_send(total_debit)` + `converter.convert(...)`.
- Фаза 2: `_balance -= / +=`.
- **Между фазами нет кода, который может упасть.**

**Retry:** `RETRYABLE_ERRORS = (AccountFrozenError,)`. `InsufficientFunds`/`AccountClosed` — не ретраятся. `ERROR_CODES`: специфичные классы первыми. `mark_failed(reason, code)` — оба аргумента обязательны.

`process_all` — по `tx.status`, не по `return value`.

## 4. `Bank`

**Порядок проверок:** время → клиент существует → не заблокирован → auth → владение счётом → delegate в `Account`.

| | `RESTRICTED_HOURS=(0,5)` | `night_hours=(22,6)` |
|---|---|---|
| Действие | Жёсткий запрет | Мягкий флаг (+1 к reasons) |
| Когда | `Bank._check_time` | `RiskAnalyzer._check_night_time` |

Пересекаются 00:00–04:59. Разные окна намеренно: запрет — узкое «ночь», флаг — широкое «вечер/утро».

**Auth:** 3 неудачи → `status="blocked"`. Успех сбрасывает `failed_attempts`.

## 5. `RiskAnalyzer`

| Правило | Порог | reasons |
|---|---|---|
| Крупная сумма | RUB 100k, USD 1k, EUR 1k, KZT 500k, CNY 7k | `"large amount: X > Y"` |
| Частые | 5+ `transaction_completed` / 10 мин | `"frequent: N ops"` |
| Новый счёт | `created_at` < 30 дней | `"new account: N days"` |
| Ночь | `(22, 6)` | `"night at HH:MM"` |

**Агрегация:** `0 → LOW`, `1–2 → MEDIUM` (warning), `3+ → HIGH` (critical + raise).

⚠️ `_check_frequency` — **только** `transaction_completed` (текущая в `processing`, не считается).
⚠️ `_check_night_time` — `tx.scheduled_at or self._now()` (иначе отложенные не получат флаг).
⚠️ `_in_window(h, start, end)`: `start==end` → пусто; `start>end` → через полночь.

## 6. `AuditLog`

- Уровни `INFO/WARNING/ERROR/CRITICAL`. В JSON — **`.name`** (`.name` + `Enum[name]` при чтении, не `.value`).
- Память: `deque(maxlen)`. Файл: JSONL append-only, лениво. `OSError` не пробрасывается.
- **`metadata` — плоско:** `audit_log.info(..., failure_code="x")`. Не `metadata={"failure_code": "x"}`.

**`event_type`:**
- INFO — `account_opened/closed/unfrozen`, `auth_success`, `transaction_completed`
- WARNING — `account_frozen`, `auth_failed`, `transaction_retry`, `risk_alert`
- ERROR — `transaction_failed`
- CRITICAL — `client_blocked`, `risk_blocked`

⚠️ HIGH-риск → **2 записи**: `risk_blocked` (CRITICAL) + `transaction_failed` (`failure_code="risk_blocked"`). Не суммировать.

## 7. `ReportBuilder`

- Типы: `CLIENT` (счета+история+риск), `BANK` (сводка+топ-5), `RISK` (алерты+блокировки).
- Форматы: TEXT, JSON (`indent=2`, `default=str`), CSV (одна «главная» таблица).
- Графики: PIE (CLIENT/BANK), BAR (все), BALANCE_FLOW (только CLIENT, требует `transactions`).

**Фильтрация:** `VALID_CHARTS_BY_TYPE` отсеивает неприменимые до `chart_*`. `plt.close(fig)` — в `finally` (иначе утечка).

⚠️ `data["key"]["subkey"]` → `(data.get("key") or {}).get("subkey")`. Структура `data` **стабильна** (`{"since": None}`, не `None`).

## 8. `scenario.py`

7 фаз: инфраструктура → клиенты → счета → 40 транзакций → симуляция (3 стадии) → сценарии клиентов → отчёты → self-checks.
