"""
Timing analyzer — Phase C3.

Analyzes engagement patterns by hour-of-day and day-of-week
to identify optimal activity windows.
"""
from collections import defaultdict
from sqlalchemy import func, extract
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class TimingAnalyzer:
    """Analyze hour/day engagement patterns from action log data."""

    def analyze(self, db) -> dict:
        """
        Return timing analysis data.

        Returns:
            {
                "hourly": {0: count, 1: count, ...},
                "daily": {"monday": count, ...},
                "hourly_success_rate": {0: rate, ...},
                "best_hours": [10, 11, 14, 15],
                "worst_hours": [0, 1, 2, 3],
                "best_days": ["tuesday", "wednesday"],
                "recommendation": "Focus activity between 10-16h on Tue-Thu",
                "total_actions": 100,
            }
        """
        from backend.storage.models import ActionLog

        try:
            # All successful actions
            rows = (
                db.query(ActionLog)
                .filter(ActionLog.result == "SUCCESS")
                .all()
            )

            if not rows:
                return self._empty_result()

            # Count by hour
            hourly = defaultdict(int)
            daily = defaultdict(int)

            for row in rows:
                if row.created_at:
                    hourly[row.created_at.hour] += 1
                    day_name = row.created_at.strftime("%A").lower()
                    daily[day_name] += 1

            # Fill missing hours/days with 0
            hourly_dict = {h: hourly.get(h, 0) for h in range(24)}
            day_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            daily_dict = {d: daily.get(d, 0) for d in day_order}

            # Success rate by hour (success / total attempts)
            all_rows = db.query(ActionLog).all()
            hour_total = defaultdict(int)
            hour_success = defaultdict(int)
            for row in all_rows:
                if row.created_at:
                    h = row.created_at.hour
                    hour_total[h] += 1
                    if row.result == "SUCCESS":
                        hour_success[h] += 1

            hourly_success_rate = {}
            for h in range(24):
                t = hour_total.get(h, 0)
                s = hour_success.get(h, 0)
                hourly_success_rate[h] = round(s / t, 3) if t > 0 else 0.0

            # Best/worst hours (by volume)
            sorted_hours = sorted(hourly_dict.items(), key=lambda x: x[1], reverse=True)
            active_hours = [(h, c) for h, c in sorted_hours if c > 0]
            best_hours = [h for h, c in active_hours[:4]]
            worst_hours = [h for h in range(24) if hourly_dict[h] == 0][:4]

            # Best days
            sorted_days = sorted(daily_dict.items(), key=lambda x: x[1], reverse=True)
            best_days = [d for d, c in sorted_days[:3] if c > 0]

            # Recommendation
            recommendation = self._build_recommendation(best_hours, best_days, len(rows))

            return {
                "hourly": hourly_dict,
                "daily": daily_dict,
                "hourly_success_rate": hourly_success_rate,
                "best_hours": best_hours,
                "worst_hours": worst_hours,
                "best_days": best_days,
                "recommendation": recommendation,
                "total_actions": len(rows),
            }

        except Exception as e:
            logger.error(f"TimingAnalyzer: analysis failed: {e}")
            return self._empty_result()

    def _build_recommendation(self, best_hours, best_days, total) -> str:
        if total < 10:
            return "Need at least 10 actions for timing analysis"

        if best_hours:
            hour_range = f"{min(best_hours):02d}:00-{max(best_hours)+1:02d}:00"
        else:
            hour_range = "09:00-17:00"

        if best_days:
            day_str = ", ".join(d.capitalize() for d in best_days[:3])
        else:
            day_str = "weekdays"

        return f"Focus activity between {hour_range} on {day_str}"

    def _empty_result(self) -> dict:
        return {
            "hourly": {h: 0 for h in range(24)},
            "daily": {d: 0 for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]},
            "hourly_success_rate": {h: 0.0 for h in range(24)},
            "best_hours": [],
            "worst_hours": [],
            "best_days": [],
            "recommendation": "No data yet",
            "total_actions": 0,
        }


# Module-level singleton
timing_analyzer = TimingAnalyzer()
