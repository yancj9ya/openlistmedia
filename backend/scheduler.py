from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import threading


@dataclass(frozen=True)
class CronField:
    values: frozenset[int]
    wildcard: bool

    def matches(self, value: int) -> bool:
        return value in self.values


@dataclass(frozen=True)
class CronExpression:
    minute: CronField
    hour: CronField
    day_of_month: CronField
    month: CronField
    day_of_week: CronField

    @classmethod
    def parse(cls, expression: str) -> "CronExpression":
        fields = expression.strip().split()
        if len(fields) != 5:
            raise ValueError("Cron expression must contain 5 fields: minute hour day month weekday")
        return cls(
            minute=_parse_field(fields[0], 0, 59),
            hour=_parse_field(fields[1], 0, 23),
            day_of_month=_parse_field(fields[2], 1, 31),
            month=_parse_field(fields[3], 1, 12),
            day_of_week=_parse_field(fields[4], 0, 6, allow_sunday_alias=True),
        )

    def matches(self, value: datetime) -> bool:
        weekday = (value.weekday() + 1) % 7
        day_of_month_match = self.day_of_month.matches(value.day)
        day_of_week_match = self.day_of_week.matches(weekday)
        if self.day_of_month.wildcard and self.day_of_week.wildcard:
            day_match = True
        elif self.day_of_month.wildcard:
            day_match = day_of_week_match
        elif self.day_of_week.wildcard:
            day_match = day_of_month_match
        else:
            day_match = day_of_month_match or day_of_week_match
        return (
            self.minute.matches(value.minute)
            and self.hour.matches(value.hour)
            and self.month.matches(value.month)
            and day_match
        )

    def next_after(self, value: datetime) -> datetime:
        candidate = value.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(366 * 24 * 60):
            if self.matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)
        raise ValueError("Unable to find next cron run within 366 days")


def validate_cron_expression(expression: str) -> None:
    CronExpression.parse(expression)


class ScheduledRefreshRunner:
    def __init__(self, service, cron_expression: str | None) -> None:
        self.service = service
        self.cron_expression = (cron_expression or "").strip()
        self.schedule = (
            CronExpression.parse(self.cron_expression) if self.cron_expression else None
        )
        self._stop_event = threading.Event()
        self._run_lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.schedule:
            print("Scheduled refresh disabled: media_wall.refresh_cron is empty.")
            return
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_loop,
            name="scheduled-refresh-runner",
            daemon=True,
        )
        self._thread.start()
        next_run = self.schedule.next_after(datetime.now())
        print(
            f"Scheduled refresh enabled with cron '{self.cron_expression}', next run at {next_run:%Y-%m-%d %H:%M}."
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def reload(self, cron_expression: str | None) -> None:
        new_cron = (cron_expression or "").strip()
        if new_cron == self.cron_expression:
            return
        self.stop()
        self._stop_event = threading.Event()
        self._run_lock = threading.Lock()
        self._thread = None
        self.cron_expression = new_cron
        self.schedule = CronExpression.parse(new_cron) if new_cron else None
        self.start()

    def _run_loop(self) -> None:
        assert self.schedule is not None
        while not self._stop_event.is_set():
            now = datetime.now()
            next_run = self.schedule.next_after(now)
            delay = max((next_run - now).total_seconds(), 1.0)
            if self._stop_event.wait(delay):
                return
            if not self._run_lock.acquire(blocking=False):
                print("Scheduled refresh skipped because a previous refresh is still running.")
                continue
            try:
                print(f"Scheduled refresh started at {datetime.now():%Y-%m-%d %H:%M:%S}.")
                summary = self.service.refresh_all_categories_shallow(force_remote_refresh=False)
                print(
                    "Scheduled refresh completed: "
                    f"{summary['refreshed_count']} categories refreshed, "
                    f"{summary['failed_count']} failures."
                )
            except Exception as exc:
                print(f"Scheduled refresh failed: {exc}")
            finally:
                self._run_lock.release()


def _parse_field(
    field: str,
    minimum: int,
    maximum: int,
    *,
    allow_sunday_alias: bool = False,
) -> CronField:
    field = field.strip()
    if not field:
        raise ValueError("Cron field cannot be empty")
    if field == "*":
        return CronField(frozenset(range(minimum, maximum + 1)), True)

    values: set[int] = set()
    for part in field.split(","):
        values.update(
            _parse_part(
                part.strip(),
                minimum,
                maximum,
                allow_sunday_alias=allow_sunday_alias,
            )
        )
    if not values:
        raise ValueError(f"Invalid cron field: {field}")
    return CronField(frozenset(values), False)


def _parse_part(
    part: str,
    minimum: int,
    maximum: int,
    *,
    allow_sunday_alias: bool = False,
) -> set[int]:
    if not part:
        raise ValueError("Cron field contains an empty segment")
    base, step_text = (part.split("/", 1) + ["1"])[:2]
    try:
        step = int(step_text)
    except ValueError as exc:
        raise ValueError(f"Invalid cron step value: {step_text}") from exc
    if step <= 0:
        raise ValueError("Cron step must be greater than 0")

    if base == "*":
        start = minimum
        end = maximum
    elif "-" in base:
        start_text, end_text = base.split("-", 1)
        start = _parse_number(
            start_text, minimum, maximum, allow_sunday_alias=allow_sunday_alias
        )
        end = _parse_number(
            end_text, minimum, maximum, allow_sunday_alias=allow_sunday_alias
        )
        if start > end:
            raise ValueError(f"Invalid cron range: {base}")
    else:
        return {
            _parse_number(
                base, minimum, maximum, allow_sunday_alias=allow_sunday_alias
            )
        }

    return set(range(start, end + 1, step))


def _parse_number(
    value: str,
    minimum: int,
    maximum: int,
    *,
    allow_sunday_alias: bool = False,
) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid cron value: {value}") from exc
    if allow_sunday_alias and number == 7:
        number = 0
    if number < minimum or number > maximum:
        raise ValueError(f"Cron value {number} out of range [{minimum}, {maximum}]")
    return number
