from src.utils.constants import RRN_LOOSE_PATTERN, RRN_STRICT_PATTERN, UI_TEXT_ELEMENTS
from src.utils.grid.checks.base_check import BaseCheck, CellIssue

UI_TEXT = UI_TEXT_ELEMENTS["grid_checks"]["common"]


class RRNCheck(BaseCheck):
    def check_cell(self, index, value: str) -> str | CellIssue:
        if value == "":
            return value

        # NOTE: loose pattern matching is allowed, we will transform it
        if RRN_LOOSE_PATTERN.match(value):
            value = f"{value[:2]}.{value[2:4]}.{value[4:6]}-{value[6:9]}.{value[9:]}"

        elif not RRN_STRICT_PATTERN.match(value):
            return (index, UI_TEXT["rrn_format_error"])

        # NOTE: check if it is a valid RRN
        digits = value[:-2].replace(".", "").replace("-", "")
        control = int(value[-2:])

        is_valid = lambda d: 97 - int(d) % 97 == control

        # NOTE: for people born after 2000, add a 2 to the digits
        if not is_valid(digits) and not is_valid(f"2{digits}"):
            return (index, UI_TEXT["rrn_invalid_error"])

        return value
