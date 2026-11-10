
from utils import InvalidOperationError


class CurrencyConverter:

    def __init__(self, rates: dict[tuple[str, str], float] | None = None):
        self.rates = rates or {}

    def convert(self, amount: float, src: str, dst: str) -> float:

        if src == dst:
            return amount

        rate = self.rates.get((src, dst))
        if rate is None:
            raise InvalidOperationError(
                f"Нет курса {src} -> {dst}. "
                f"Доступные пары: {list(self.rates.keys())}"
            )

        return round(amount * rate, 2)

    def add_rate(self, src: str, dst: str, rate: float) -> None:
    
        if rate <= 0:
            raise InvalidOperationError(f"Курс должен быть > 0, получено {rate}")
        self.rates[(src, dst)] = rate