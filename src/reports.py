import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable
from collections import Counter, defaultdict
from utils import ClientNotFoundError, InvalidOperationError, AccountNotFoundError
import matplotlib
matplotlib.use("Agg")                  
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from currency_converter import CurrencyConverter
import logging

logger = logging.getLogger(__name__)

from models import AuditLevel, AuditLog
from models import Bank
from models import BankAccount, Transaction

class ReportType(Enum):
    CLIENT = "client"
    BANK = "bank"
    RISK = "risk"


class ReportFormat(Enum):
    TEXT = "text"
    JSON = "json"
    CSV = "csv"


class ChartType(Enum):
    PIE = "pie"                  
    BAR = "bar"                  
    BALANCE_FLOW = "balance_flow"  

class ReportBuilder:
    VALID_CHARTS_BY_TYPE = {
        ReportType.CLIENT: {ChartType.PIE, ChartType.BAR, ChartType.BALANCE_FLOW},
        ReportType.BANK:   {ChartType.PIE, ChartType.BAR},
        ReportType.RISK:   {ChartType.BAR},          
    }
    def __init__(
        self,
        bank: Bank,
        audit_log: AuditLog,
        output_dir: str | Path = "reports",
        now_provider: Callable[[], datetime] | None = None,
        dpi: int = 100,
        figsize: tuple[float, float] = (10, 6), converter=None
    ):
        self.bank = bank
        self.audit_log = audit_log
        
        self.output_dir: Path = Path(output_dir) 
        self.now = now_provider or datetime.now 
        self.dpi = dpi
        self.figsize = figsize
        self._now = now_provider or datetime.now 
        self.converter = converter or CurrencyConverter({
        ("USD", "RUB"): 90.0, ("RUB", "USD"): 0.011,
        ("EUR", "RUB"): 100.0, ("RUB", "EUR"): 0.010,
        ("USD", "EUR"): 0.92, ("EUR", "USD"): 1.09,
    })
    def _collect_client_report(self, client_id: str) -> dict:
        from collections import Counter, defaultdict

    # ─── 1. Клиент ───
        client = self.bank.clients.get(client_id)
        if client is None:
            raise ClientNotFoundError(f"Client {client_id} not found")

    # ─── 2. Счета клиента ───
        accounts_data: list[dict] = []
        total_by_currency: dict[str, float] = defaultdict(float)
        for aid in client.account_ids:
            acc = self.bank.accounts.get(aid)
            if acc is None:
                continue
            accounts_data.append({
            "account_id": acc.account_id,
            "type": type(acc).__name__,
            "currency": acc.currency,
            "balance": acc.balance,
            "status": acc.status,
            "created_at": acc.created_at.isoformat() if acc.created_at else None,
            })
            if acc.status != "closed":
                total_by_currency[acc.currency] += acc.balance

   
        completed = self.audit_log.get_entries(
            event_type="transaction_completed", client_id=client_id,
        )
        failed = self.audit_log.get_entries(
            event_type="transaction_failed", client_id=client_id,
        )
        retried = self.audit_log.get_entries(
            event_type="transaction_retry", client_id=client_id,
        )
        risk_blocked = self.audit_log.get_entries(
            event_type="risk_blocked", client_id=client_id,
        )
        all_tx_ids: set[str] = {
            e.transaction_id
            for e in completed + failed
            if e.transaction_id
        }

    # ─── 5. by_type (из metadata["tx_type"]) ───
        by_type: Counter[str] = Counter()
        for e in completed + failed + risk_blocked:
            tx_type = e.metadata.get("tx_type")
            if tx_type:
                by_type[tx_type] += 1

    # ─── 6. Последние 10 событий ───
        recent = self.audit_log.get_entries(
            client_id=client_id, limit=10, reverse=True,
        )

        return {
        "report_type": "client",
        "generated_at": self._now().isoformat(),
        "client": {
            "client_id": client.client_id,
            "full_name": client.full_name,
            "status": client.status,
            "contacts": dict(client.contacts),
            "suspicious": client.suspicious_activity,
        },
        "accounts": accounts_data,
        "total_balance_by_currency": dict(total_by_currency),
        "transactions": {
            "total": len(all_tx_ids),              # ✅ без двойного счёта
            "completed": len(completed),
            "failed": len(failed),
            "risk_blocked": len(risk_blocked),     # информационно; входит в failed
            "retried": len(retried),
            "by_type": dict(by_type),
            "recent": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "level": e.level.name,
                    "event_type": e.event_type,
                    "message": e.message,
                    "tx_id": e.transaction_id,
                }
                for e in recent
            ],
        },
        "risk_profile": self.bank.report_client_risk_profile(client_id),
    }
       

    def _collect_bank_report(self) -> dict:


        status_counter: Counter[str] = Counter()
        balances: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0})

        for acc in self.bank.accounts.values():
            status_counter[acc.status] += 1
            if acc.status != "closed":
                balances[acc.currency]["total"] += acc.balance
                balances[acc.currency]["count"] += 1

        completed = self.audit_log.get_entries(event_type="transaction_completed")
        failed = self.audit_log.get_entries(event_type="transaction_failed")
        retries = self.audit_log.get_entries(event_type="transaction_retry")

        completed_ids: set[str] = {
        e.transaction_id for e in completed if e.transaction_id
        }
        failed_ids: set[str] = {
        e.transaction_id for e in failed if e.transaction_id
        }
        by_type: Counter[str] = Counter()
        seen_for_type: set[str] = set()
        for e in completed + failed:
            if not e.transaction_id or e.transaction_id in seen_for_type:
                continue
            seen_for_type.add(e.transaction_id)
            tx_type = e.metadata.get("tx_type")
            if tx_type:
                by_type[tx_type] += 1

        by_failure_code: Counter[str] = Counter()
        for e in failed:
            code = e.metadata.get("failure_code", "unknown")
            by_failure_code[code] += 1

        ranking = self.bank.get_clients_ranking()[:5]
        top_clients: list[dict] = []
        for client, totals_by_currency in ranking:
            unconverted = []
            for ccy in totals_by_currency:
                if ccy == self.bank.base_currency:
                    continue
                try:
                    self.bank.converter.convert(1.0, ccy, self.bank.base_currency)
                except InvalidOperationError:
                    unconverted.append(ccy)
            top_clients.append({
            "client_id": client.client_id,
            "full_name": client.full_name,
            "accounts_count": len(client.account_ids),
            "total_by_currency": dict(totals_by_currency),  
            "unconverted_currencies": unconverted,        # ← добавить
            "ranking_warning": (
                f"Нет курса: {', '.join(unconverted)}" if unconverted else None
            ), 
            })

        return {
            "report_type": "bank",
            "generated_at": self._now().isoformat(),

  
            "summary": {
                "total_clients": len(self.bank.clients),
                "total_accounts": len(self.bank.accounts),
                "active_accounts": status_counter.get("active", 0),
                "frozen_accounts": status_counter.get("frozen", 0),
                "closed_accounts": status_counter.get("closed", 0),
            },

   
            "balances_by_currency": {
                ccy: {"total": round(info["total"], 2), "count": info["count"]}
                for ccy, info in sorted(balances.items())
            },

       
            "transaction_stats": {
                "total": len(completed_ids) + len(failed_ids),  
                "completed": len(completed_ids),
                "failed": len(failed_ids),
                "cancelled": 0,                          
                "retries": len(retries),
                "by_type": dict(by_type),
                "by_failure_code": dict(by_failure_code),
            },

     
            "top_clients": top_clients,

        
            "audit_stats": {
                "total_entries": len(self.audit_log),
                "by_level": {
                    lvl.name: cnt
                    for lvl, cnt in self.audit_log.count_by_level().items()
                },
                "by_event_type": self.audit_log.count_by_event_type(),
            },
        }

    def _collect_risk_report(self, since: datetime | None = None) -> dict:
        alerts = self.audit_log.get_entries(event_type="risk_alert", since=since)
        blocked = self.audit_log.get_entries(event_type="risk_blocked", since=since)
        def _view(e) -> dict:
            return {
                "tx_id": e.transaction_id,
                "risk_level": e.metadata.get("risk_level", "unknown"),
                "reasons": list(e.metadata.get("reasons", [])),
                "timestamp": e.timestamp.isoformat(),
         }
        by_client: dict[str, dict] = {}
        affected: set[str] = set()

        def _bucket(cid: str) -> dict:
            if cid not in by_client:
                client = self.bank.clients.get(cid) if cid != "unknown" else None
                by_client[cid] = {
                    "client_name": client.full_name if client else None,
                    "alerts": [],
                    "blocked": [],
                    "risk_level_counts": Counter(),
                }
            return by_client[cid]

        for e in alerts:
            cid = e.client_id or "unknown"
            _bucket(cid)["alerts"].append(_view(e))
            _bucket(cid)["risk_level_counts"][e.metadata.get("risk_level", "unknown")] += 1
            affected.add(cid)

        for e in blocked:
            cid = e.client_id or "unknown"
            _bucket(cid)["blocked"].append(_view(e))
            _bucket(cid)["risk_level_counts"][e.metadata.get("risk_level", "unknown")] += 1
            affected.add(cid)

        for bucket in by_client.values():
            bucket["risk_level_counts"] = dict(bucket["risk_level_counts"])


        reasons_counter: Counter[str] = Counter()
        for e in alerts + blocked:
            for reason in e.metadata.get("reasons", []):
                reasons_counter[reason] += 1

        blocked_txs = [
            {
                "tx_id": e.transaction_id,
                "client_id": e.client_id,
                "reasons": list(e.metadata.get("reasons", [])),
                "timestamp": e.timestamp.isoformat(),
            }
            for e in blocked
        ]
        return {
            "report_type": "risk",
            "generated_at": self._now().isoformat(),
            "period": {
                "since": since.isoformat() if since else None,   
                },
            "summary": {
                "total_alerts": len(alerts),
                "total_blocked": len(blocked),
                "affected_clients": len(affected), 
            },
            "by_client": by_client,
            "top_reasons": [
                {"reason": r, "count": c}
                for r, c in reasons_counter.most_common(10)
                ],
            "blocked_transactions": blocked_txs,
            "thresholds": dict(self.bank.risk_analyzer.thresholds),
            }

    def _collect(self, report_type: ReportType, client_id: str | None = None) -> dict:
        if report_type is ReportType.CLIENT:
            if client_id is None:
                raise InvalidOperationError("client_id is required for CLIENT report")
            return self._collect_client_report(client_id)          

        if report_type is ReportType.BANK:
            return self._collect_bank_report()                     

        if report_type is ReportType.RISK:
            return self._collect_risk_report()                     

        raise InvalidOperationError(f"Unknown report type: {report_type}")


    def render_text(self, report_type: ReportType, client_id: str | None = None) -> str:
        data = self._collect(report_type, client_id=client_id)
        if report_type is ReportType.CLIENT:
            return self._render_client_text(data)
        if report_type is ReportType.BANK:
            return self._render_bank_text(data)
        if report_type is ReportType.RISK:
            return self._render_risk_text(data)
        raise InvalidOperationError(f"Unknown report type: {report_type}")

   
    @staticmethod
    def _fmt_money(value: float, currency: str = "") -> str:
        suffix = f" {currency}" if currency else ""
        return f"{value:>15,.2f}{suffix}"

    @staticmethod
    def _short_id(value: str | None) -> str:
        if not value:
            return "—"
        return f"***{value[-4:]}" if len(value) > 4 else value

    @staticmethod
    def _hr(width: int = 68) -> str:
        return "═" * width

   
    def _render_client_text(self, data: dict) -> str:
        lines: list[str] = []
        client = data["client"]

        lines.append(self._hr())
        lines.append(f"  Client report: {client['full_name']} ({client['client_id']})")
        lines.append(f"  Generated at: {data['generated_at']}")
        if client.get("suspicious"):
            lines.append("Client is marked as suspicious")
        lines.append(self._hr())

        accounts = data["accounts"]
        lines.append(f"\naccounts ({len(accounts)}):")
        if not accounts:
            lines.append("  (no opened accounts)")
        else:
            lines.append(
                f"  {'ID':>10s}  {'Тип':<16s} {'Валюта':<6s} "
                f"{'Баланс':>15s}  {'Статус':<10s}"
            )
            for acc in accounts:
                acc_type = acc["type"].replace("Account", "")
                lines.append(
                    f"  {self._short_id(acc['account_id']):>10s}  "
                    f"{acc_type:<16s} {acc['currency']:<6s} "
                    f"{acc['balance']:>15,.2f}  {acc['status']:<10s}"
                )

        totals = data["total_balance_by_currency"]
        lines.append("Balance by currency:")
        if not totals:
            lines.append("  (empty)")
        else:
            for ccy, total in sorted(totals.items()):
                lines.append(f"  {ccy}: {total:>15,.2f}")

        
        tx = data["transactions"]
        lines.append(
            f"transactions: all {tx['total']} | "
            f"completed {tx['completed']} | failed {tx['failed']} | "
            f"risk_blocked {tx['risk_blocked']} | retried {tx['retried']}"
        )
        if tx["by_type"]:
            by_type = ", ".join(f"{k}={v}" for k, v in sorted(tx["by_type"].items()))
            lines.append(f"  By type: {by_type}")

        
        rp = data.get("risk_profile") or {}
        dist = rp.get("risk_distribution", {})
        lines.append("risk_profile:")
        lines.append(
            f"  low={dist.get('low', 0)} medium={dist.get('medium', 0)} "
            f"high={dist.get('high', 0)} | blocked: {rp.get('blocked_count', 0)}"
        )
        top = rp.get("top_reasons", [])
        if top:
            lines.append("top reasons:")
            for item in top[:5]:
                lines.append(f"    - {item['reason']} — {item['count']} раз")

        recent = tx.get("recent", [])
        if recent:
            lines.append(f"recent events({len(recent)}):")
            for e in recent:
                ts = e["timestamp"][11:16]  
                lines.append(f"  [{ts}] {e['level']:<8s} {e['event_type']}: {e['message'][:60]}")

        return "\n".join(lines)


    def _render_bank_text(self, data: dict) -> str:
        lines: list[str] = []

        lines.append(self._hr())
        lines.append("  Bank report")
        lines.append(f"  Generated at: {data['generated_at']}")
        lines.append(self._hr())

        
        s = data["summary"]
        lines.append("Summary:")
        lines.append(f"  Clients:        {s['total_clients']}")
        lines.append(f"  Accounts:          {s['total_accounts']}")
        lines.append(f"    Active:      {s['active_accounts']}")
        lines.append(f"    Frozen:  {s['frozen_accounts']}")
        lines.append(f"    Blocked:      {s['closed_accounts']}")

        lines.append("balances_by_currency:")
        balances = data["balances_by_currency"]
        if not balances:
            lines.append("  (no data)")
        else:
            for ccy, info in balances.items():
                lines.append(
                    f"  {ccy}: {info['total']:>15,.2f}  ({info['count']} accounts)"
                )

      
        ts = data["transaction_stats"]
        lines.append("transaction_stats:")
        lines.append(f"  all:         {ts['total']}")
        lines.append(f"  success:      {ts['completed']}")
        lines.append(f"  denied:   {ts['failed']}")
        lines.append(f"  Retry:         {ts['retries']}")
        if ts["by_type"]:
            by_type = ", ".join(f"{k}={v}" for k, v in sorted(ts["by_type"].items()))
            lines.append(f"  By type:      {by_type}")
        if ts["by_failure_code"]:
            by_code = ", ".join(
                f"{k}={v}" for k, v in sorted(ts["by_failure_code"].items())
            )
            lines.append(f"  By mistakes:    {by_code}")

        
        lines.append("Top 5 clients:")
        for i, c in enumerate(data["top_clients"], 1):
            per_ccy = ", ".join(
                f"{v:,.2f} {k}" for k, v in sorted(c["total_by_currency"].items())
            ) or "—"
            warning = f" {c['ranking_warning']}" if c.get("ranking_warning") else ""
            lines.append(
                f"  {i}. {c['full_name']:<25s} — {per_ccy} "
                f"({c['accounts_count']} счетов)"
            )

        
        a = data["audit_stats"]
        lines.append("Audit:")
        lines.append(f"  All: {a['total_entries']}")
        by_lvl = ", ".join(f"{k}={v}" for k, v in a["by_level"].items())
        lines.append(f"  By level:    {by_lvl}")
        top_events = sorted(a["by_event_type"].items(), key=lambda x: -x[1])[:5]
        if top_events:
            top_str = ", ".join(f"{k}={v}" for k, v in top_events)
            lines.append(f" Top events:   {top_str}")

        return "\n".join(lines)

   
    def _render_risk_text(self, data: dict) -> str:
        lines: list[str] = []

        lines.append(self._hr())
        lines.append("  Risk report")
        lines.append(f"  Generated at: {data['generated_at']}")
        if data["period"]["since"]:
            lines.append(f"  Period from: {data['period']['since']}")
        lines.append(self._hr())

       
        s = data["summary"]
        lines.append("summary:")
        lines.append(f"  All:         {s['total_alerts']}")
        lines.append(f"  Blocked:         {s['total_blocked']}")
        lines.append(f"  affected clients:    {s['affected_clients']}")

       
        lines.append("by_client:")
        by_client = data["by_client"]
        if not by_client:
            lines.append("  (no risk events)")
        else:
            for cid, info in by_client.items():
                name = info.get("client_name") or "(unknown)"
                counts = info.get("risk_level_counts", {})
                counts_str = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
                lines.append(
                    f"  {name:<25s} ({cid[:8]}): "
                    f"alerts={len(info['alerts'])}, blocked={len(info['blocked'])} | "
                    f"{counts_str}"
                )
                
                for a in info["alerts"][:3]:
                    reasons = "; ".join(a["reasons"])[:60]
                    lines.append(f"    [{a['risk_level']:>6s}] {a['tx_id']}: {reasons}")
                if len(info["alerts"]) > 3:
                    lines.append(f"    and more {len(info['alerts']) - 3} alerts")

        
        lines.append("top 10 reasons:")
        top = data["top_reasons"]
        if not top:
            lines.append("  (no reasons)")
        else:
            for i, item in enumerate(top, 1):
                lines.append(f"  {i:2d}. {item['reason']} — {item['count']}")

        
        blocked = data["blocked_transactions"]
        lines.append(f"blocked_transactions ({len(blocked)}):")
        if not blocked:
            lines.append("  (no)")
        else:
            for b in blocked[:10]:
                reasons = "; ".join(b["reasons"])[:70]
                cid = self._short_id(b["client_id"])
                lines.append(f"  {b['tx_id']:<8s} client={cid}: {reasons}")
            if len(blocked) > 10:
                lines.append(f"  and more {len(blocked) - 10}")

      
        th = data.get("thresholds") or {}
        if th:
            lines.append("thresholds:")
            for k, v in th.items():
                lines.append(f"  {k}: {v}")

        return "\n".join(lines)


    def _ensure_output_dir(self) -> Path:
       
        p = Path(self.output_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _make_filename(self, base: str, ext: str) -> Path:
    
        ts = self._now().strftime("%Y%m%d_%H%M%S")
        return self._ensure_output_dir() / f"{base}_{ts}.{ext}"

    # ---------- JSON ----------
    def export_to_json(
        self,
        report_type: ReportType,
        client_id: str | None = None,
        filename: str | None = None,
    ) -> Path:

        data = self._collect(report_type, client_id=client_id)

        if filename is None:
            base = f"{report_type.value}_{client_id or 'all'}"
            path = self._make_filename(base, "json")
        else:
            path = self._ensure_output_dir() / filename

        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        return path

    
    def export_to_csv(
        self,
        report_type: ReportType,
        client_id: str | None = None,
        filename: str | None = None,
    ) -> Path:

        data = self._collect(report_type, client_id=client_id)

        if report_type is ReportType.CLIENT:
            rows = self._rows_for_client_csv(data)
        elif report_type is ReportType.BANK:
            rows = self._rows_for_bank_csv(data)
        elif report_type is ReportType.RISK:
            rows = self._rows_for_risk_csv(data)
        else:
            raise InvalidOperationError(f"Unknown report type: {report_type}")

        if filename is None:
            base = f"{report_type.value}_{client_id or 'all'}"
            path = self._make_filename(base, "csv")
        else:
            path = self._ensure_output_dir() / filename

        
        if not rows:
            path.write_text("(no data)\n", encoding="utf-8")
            return path

        fieldnames = list(rows[0].keys())
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        return path


    def _rows_for_client_csv(self, data: dict) -> list[dict]:
      
        rows: list[dict] = []
        client = data["client"]
        for acc in data["accounts"]:
            rows.append({
                "client_id": client["client_id"],
                "client_name": client["full_name"],
                "account_id": acc["account_id"],
                "account_type": acc["type"],
                "currency": acc["currency"],
                "balance": acc["balance"],
                "status": acc["status"],
                "created_at": acc["created_at"] or "",
            })
        return rows

    def _rows_for_bank_csv(self, data: dict) -> list[dict]:

        top = data["top_clients"]
        if not top:
            return []

        
        all_ccy = sorted({
            ccy for c in top for ccy in c["total_by_currency"].keys()
        })

        rows: list[dict] = []
        for c in top:
            row = {
                "client_id": c["client_id"],
                "full_name": c["full_name"],
                "accounts_count": c["accounts_count"],
            }
            for ccy in all_ccy:
                row[f"balance_{ccy}"] = c["total_by_currency"].get(ccy, 0.0)
            rows.append(row)
        return rows

    def _rows_for_risk_csv(self, data: dict) -> list[dict]:

        rows: list[dict] = []
        for b in data["blocked_transactions"]:
            rows.append({
                "tx_id": b["tx_id"],
                "client_id": b["client_id"] or "",
                "timestamp": b["timestamp"],
                "reasons": "; ".join(b["reasons"]),
            })
        return rows

    def chart_balance_pie(
        self,
        report_type: ReportType,
        client_id: str | None = None,
        by: str = "currency",       
        title: str | None = None,
    ) -> Figure:
        if by not in ("currency", "account_type"):
            raise InvalidOperationError(
            f"by must be 'currency' or 'account_type', got {by!r}"
            )
        if report_type is ReportType.RISK:
            raise InvalidOperationError(
            "Risk report has no balances to plot — use chart_transactions_bar"
        )

        data = self._collect(report_type, client_id=client_id)

        grouped: dict[str, float] = defaultdict(float)

        if report_type is ReportType.CLIENT:
            for acc in data["accounts"]:
                if acc["status"] == "closed":
                    continue
                key = acc["currency"] if by == "currency" else self._short_account_type(acc["type"])
                grouped[key] += acc["balance"]

        elif report_type is ReportType.BANK:
            if by == "currency":
                for ccy, info in data["balances_by_currency"].items():
                    grouped[ccy] = info["total"]
            else:
            
                for acc in self.bank.accounts.values():
                    if acc.status == "closed":
                        continue
                    key = self._short_account_type(type(acc).__name__)
                    grouped[key] += acc.balance

        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)

        items = [(k, v) for k, v in grouped.items() if v > 0]
        total = sum(v for _, v in items)

        if total <= 0 or not items:
            ax.text(
                0.5, 0.5, "Нет данных для отображения",
                ha="center", va="center", fontsize=14, color="gray",
            )
            ax.axis("off")
        else:
            labels = [k for k, _ in items]
            values = [v for _, v in items]
            colors = self._pie_colors(by, labels)

            ax.pie(
                values,
                labels=labels,
                colors=colors,
                autopct="%1.1f%%",
                startangle=90,
                wedgeprops={"edgecolor": "white", "linewidth": 1.5},
                textprops={"fontsize": 11},
            )
        
            ax.legend(
                [f"{lbl}: {val:,.2f}" for lbl, val in zip(labels, values)],
                loc="upper left",
                bbox_to_anchor=(1.02, 1.0),
                frameon=False,
                fontsize=10,
            )

        default_title = (
         f"Распределение баланса по {'валютам' if by == 'currency' else 'типам счетов'}"
        )
        ax.set_title(title or default_title, fontsize=13)
        fig.tight_layout()
        return fig
    @staticmethod
    def _short_account_type(type_name: str) -> str:
        mapping = {
            "BankAccount": "basic",
            "SavingsAccount": "savings",
            "PremiumAccount": "premium",
            "InvestmentAccount": "investment",
        }
        if type_name in mapping:
            return mapping[type_name]
        return type_name.replace("Account", "").lower() or "unknown"


    @staticmethod
    def _pie_colors(by: str, labels: list[str]) -> list:
    
        if by == "currency":
            palette = {
            "RUB": "#4CAF50",   
            "USD": "#2196F3",   
            "EUR": "#FF9800",  
            "KZT": "#9C27B0",   
            "CNY": "#F44336",  
        }
            return [palette.get(lbl, "#9E9E9E") for lbl in labels]
    
        return plt.cm.tab10.colors[:len(labels)]

    def chart_transactions_bar(
    self,
    report_type: ReportType,
    client_id: str | None = None,
    by: str = "status",         
    title: str | None = None,
) -> Figure:

        if by not in ("status", "type", "failure_code"):
            raise InvalidOperationError(
                f"by must be 'status'/'type'/'failure_code', got {by!r}"
            )

        data = self._collect(report_type, client_id=client_id)

        if report_type is ReportType.CLIENT:
            tx = data["transactions"]
            if by == "status":
                counter = {
                "completed": tx["completed"],
                "failed": tx["failed"],
                "risk_blocked": tx["risk_blocked"],
            }
            elif by == "type":
                counter = dict(tx["by_type"])
            else:
                failed = self.audit_log.get_entries(
                    event_type="transaction_failed", client_id=client_id,
                )
                counter = dict(Counter(
                    e.metadata.get("failure_code", "unknown") for e in failed
                ))
        elif report_type is ReportType.BANK:
            ts = data["transaction_stats"]
            if by == "status":
                counter = {
                "completed": ts["completed"],
                "failed": ts["failed"],
                "retries": ts["retries"],
            }
            elif by == "type":
                counter = dict(ts["by_type"])
            else:
                counter = dict(ts["by_failure_code"])
        else: 
            if by == "status":
                counter = {
                    "alerts": data["summary"]["total_alerts"],
                 "blocked": data["summary"]["total_blocked"],
                }
            elif by == "type":
                raise InvalidOperationError("RISK report has no 'type' breakdown")
            else:
           
                counter = {item["reason"][:40]: item["count"]
                       for item in data["top_reasons"][:10]}

    
        counter = {k: v for k, v in counter.items() if v > 0}

        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)

        if not counter:
            ax.text(0.5, 0.5, "Нет данных", ha="center", va="center",
                fontsize=14, color="gray")
            ax.axis("off")
        else:
            labels = list(counter.keys())
            values = list(counter.values())

    
            if by == "status":
                palette = {"completed": "#4CAF50", "failed": "#F44336",
                       "risk_blocked": "#FF9800", "retries": "#FFC107",
                       "alerts": "#FF9800", "blocked": "#F44336"}
                colors = [palette.get(lbl, "#9E9E9E") for lbl in labels]
            else:
                colors = plt.cm.tab10.colors[:len(labels)]

            bars = ax.bar(labels, values, color=colors,
                      edgecolor="white", linewidth=1.5)
            ax.bar_label(bars, fmt="%d", padding=3, fontsize=10)
            ax.set_ylabel("Количество")
            plt.setp(ax.get_xticklabels(), rotation=20, ha="right")

        titles = {"status": "по статусам", "type": "по типам",
              "failure_code": "по кодам ошибок"}
        ax.set_title(title or f"Транзакции {titles[by]}", fontsize=13)
        fig.tight_layout()
        return fig
        

    def chart_balance_flow(
    self,
    client_id: str,
    account_id: str | None = None,
    transactions: list[Transaction] | None = None,
    title: str | None = None,
    ) -> Figure:
        client = self.bank.clients.get(client_id)
        if client is None:
            raise ClientNotFoundError(f"Client {client_id} not found")

        if account_id is None:
            candidates = [
                aid for aid in client.account_ids
                if aid in self.bank.accounts
                and self.bank.accounts[aid].status != "closed"
            ]
            if not candidates:
                return self._empty_chart("У клиента нет активных счетов")
            rub = [aid for aid in candidates if self.bank.accounts[aid].currency == "RUB"]
            account_id = rub[0] if rub else candidates[0]

        if account_id not in client.account_ids:
            raise InvalidOperationError(
                f"Account {account_id} doesn't belong to client {client_id}"
            )

        account = self.bank.accounts.get(account_id)
        if account is None:
            raise AccountNotFoundError(f"Account {account_id} not found")

        if transactions is None:
            return self._empty_chart("Недостаточно данных: передайте transactions для графа движения")

        relevant = [
            tx for tx in transactions
            if tx.status == "completed"
            and (tx.from_account_id == account_id or tx.to_account_id == account_id)
        ]
        relevant.sort(key=lambda t: t.processed_at or t.created_at)

    
        balance = account.balance
        points: list[tuple[datetime, float]] = [(self._now(), balance)]

        for tx in reversed(relevant):
            if tx.from_account_id == account_id and tx.to_account_id == account_id:
                continue  
            if tx.from_account_id == account_id:
                balance += tx.total_debit
            elif tx.to_account_id == account_id:
                if tx.currency == account.currency:
                    converted = tx.amount
                else:
                    try:
                        converted = self.converter.convert(tx.amount, tx.currency, account.currency)
                    except InvalidOperationError as exc:
                        logger.warning("Skipping tx %s in balance flow: %s", tx.id, exc)
                        continue
                balance -= converted
            points.append((tx.processed_at or tx.created_at, balance))

        points.reverse()

        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)

        if len(points) < 2:
            ax.text(0.5, 0.5, "Недостаточно данных для графа движения",
                ha="center", va="center", fontsize=13, color="gray")
            ax.axis("off")
        else:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            ax.plot(xs, ys, marker="o", linestyle="-",
                linewidth=2, markersize=5, color="#2196F3")
            ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))
            plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
            ax.set_ylabel(f"Баланс ({account.currency})")
            ax.grid(True, alpha=0.3)

        ax.set_title(
            title or f"Движение баланса: {client.full_name} / {account_id[-4:]}",
        fontsize=13,
        )
        fig.tight_layout()
        return fig


    def _empty_chart(self, message: str) -> Figure:
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
        ax.text(0.5, 0.5, message, ha="center", va="center",
            fontsize=13, color="gray")
        ax.axis("off")
        fig.tight_layout()
        return fig

    def _save_figure(self, fig: Figure, path: Path) -> Path:
   
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        return path

    def save_charts(self, report_type, client_id=None, charts=None, transactions=None):
        if charts is None:
            charts = {
            ReportType.CLIENT: [ChartType.PIE, ChartType.BAR, ChartType.BALANCE_FLOW],
            ReportType.BANK:   [ChartType.PIE, ChartType.BAR],
            ReportType.RISK:   [ChartType.BAR],
            }.get(report_type, [])

        if report_type is ReportType.RISK:
            charts = [c for c in charts if c is not ChartType.PIE]

        paths: list[Path] = []
        ts = self._now().strftime("%Y%m%d_%H%M%S")
        base = f"{report_type.value}_{client_id or 'all'}"

        for chart_type in charts:
            fig = None
            try:
                if chart_type is ChartType.PIE:
                    fig = self.chart_balance_pie(report_type, client_id=client_id)
                elif chart_type is ChartType.BAR:
                    fig = self.chart_transactions_bar(report_type, client_id=client_id)
                elif chart_type is ChartType.BALANCE_FLOW:
                    fig = self.chart_balance_flow(client_id, transactions=transactions)

                if fig is not None:
                    path = self._ensure_output_dir() / f"{base}_{chart_type.value}_{ts}.png"
                    paths.append(self._save_figure(fig, path))
            finally:
                if fig is not None:
                    plt.close(fig)       

        return paths

    def build_report(
    self,
    report_type: ReportType,
    client_id: str | None = None,
    formats: list[ReportFormat] | None = None,
    charts: list[ChartType] | None = None,
    transactions: list[Transaction] | None = None,
    ) -> dict:
        if formats is None:
         formats = [ReportFormat.TEXT, ReportFormat.JSON, ReportFormat.CSV]

        data = self._collect(report_type, client_id=client_id)
        result: dict = {"data": data, "files": [], "charts": [], "text": None}

        if ReportFormat.TEXT in formats:
            result["text"] = self.render_text(report_type, client_id=client_id)

        if ReportFormat.JSON in formats:
            result["files"].append(
            self.export_to_json(report_type, client_id=client_id)
        )

        if ReportFormat.CSV in formats:
            result["files"].append(
            self.export_to_csv(report_type, client_id=client_id)
        )

        if charts:
            result["charts"] = self.save_charts(
            report_type, client_id=client_id,
            charts=charts, transactions=transactions,
        )

        return result

    def run_all_reports(
    self,
    client_ids: list[str],
    transactions: list[Transaction] | None = None,
    ) -> dict:
    
        all_charts = [ChartType.PIE, ChartType.BAR]
        client_charts = [ChartType.PIE, ChartType.BAR, ChartType.BALANCE_FLOW]

        return {
        "bank": self.build_report(
            ReportType.BANK, charts=all_charts,
        ),
        "risk": self.build_report(
            ReportType.RISK, charts=[ChartType.BAR],
        ),
        "clients": {
            cid: self.build_report(
                ReportType.CLIENT, client_id=cid,
                formats=[ReportFormat.JSON],
                charts=client_charts,
                transactions=transactions,
            )
            for cid in client_ids
        },
    }
        
