"""Check a fleet catch log against the co-op's local species rules."""

import math
import sys


def read_text(path):
    # utf-8-sig also accepts files that start with a byte-order mark.
    with open(path, encoding="utf-8-sig") as handle:
        return handle.read()


def useful_lines(text):
    # splitlines() handles both "\n" and the "\r\n" that Windows editors save.
    for number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if line and not line.startswith("#"):
            yield number, line


def positive_number(text):
    value = float(text)
    # float() accepts "nan" and "inf"; neither is a usable measurement.
    if not math.isfinite(value) or value <= 0:
        raise ValueError(text)
    return value


def parse_rules(text):
    """Turn 'species, min length cm, max per day, min weight kg' lines into a dict."""
    rules = {}
    for number, line in useful_lines(text):
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 4 or not parts[0]:
            raise ValueError(f"rules line {number}: expected 4 fields, got {line!r}")
        try:
            min_length = positive_number(parts[1])
            max_per_day = int(parts[2])
            min_weight = positive_number(parts[3])
        except ValueError as error:
            raise ValueError(f"rules line {number}: bad number in {line!r}") from error
        if max_per_day < 0:
            raise ValueError(f"rules line {number}: daily limit cannot be negative")
        rules[parts[0].lower()] = {
            "min_length": min_length,
            "max_per_day": max_per_day,
            "min_weight": min_weight,
        }
    if not rules:
        raise ValueError("rules file contains no species rules")
    return rules


def parse_entry(line):
    """Return (species, length, weight) or raise ValueError with a reason."""
    parts = [part.strip() for part in line.split(",")]
    if len(parts) != 3:
        raise ValueError(f"expected 3 fields, got {len(parts)}")
    species, length_text, weight_text = parts
    if not species:
        raise ValueError("species is missing")
    try:
        length = positive_number(length_text)
    except ValueError:
        raise ValueError(
            f"length {length_text!r} is not a positive number"
        ) from None
    try:
        weight = positive_number(weight_text)
    except ValueError:
        raise ValueError(
            f"weight {weight_text!r} is not a positive number"
        ) from None
    return species.lower(), length, weight


def check_catch(log_text, rules):
    """Return (verdict lines, fish totals per species, rejected count)."""
    verdicts = []
    totals = {}
    kept = {}
    rejected = 0

    for number, line in useful_lines(log_text):
        try:
            species, length, weight = parse_entry(line)
        except ValueError as error:
            verdicts.append(f"line {number}: MALFORMED ({error}): {line}")
            rejected += 1
            continue

        totals[species] = totals.get(species, 0) + 1
        rule = rules.get(species)
        problems = []
        if rule is None:
            problems.append("species unknown")
        else:
            if length < rule["min_length"]:
                problems.append(
                    f"too short ({length:g} cm < {rule['min_length']:g} cm)"
                )
            if weight < rule["min_weight"]:
                problems.append(
                    f"too light ({weight:g} kg < {rule['min_weight']:g} kg)"
                )

            # Only fish that pass the size checks are landed and use up the quota.
            if not problems:
                if kept.get(species, 0) >= rule["max_per_day"]:
                    problems.append(
                        f"daily limit exceeded (max {rule['max_per_day']} {species})"
                    )
                else:
                    kept[species] = kept.get(species, 0) + 1

        if problems:
            verdicts.append(
                f"line {number}: REJECTED – {'; '.join(problems)}: {line}"
            )
            rejected += 1
        else:
            verdicts.append(f"line {number}: OK: {line}")

    return verdicts, totals, rejected


def build_report(log_text, rules):
    """Check a catch log and format its verdicts and totals as a report."""
    verdicts, totals, rejected = check_catch(log_text, rules)
    lines = list(verdicts)
    lines.append("Summary")
    for index, (species, count) in enumerate(sorted(totals.items())):
        prefix = "" if index == 0 else "  "
        lines.append(f"{prefix}{species}: {count} fish")
    if not totals:
        lines.append("  no valid catch entries")
    lines.append(f"rejected entries: {rejected}")
    return "\n".join(lines)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) > 2:
        print("Usage: python catchcheck.py [catch-log] [rules-file]", file=sys.stderr)
        return 2

    log_path = argv[0] if argv else "catch_log.txt"
    rules_path = argv[1] if len(argv) == 2 else "rules.txt"

    try:
        log_text = read_text(log_path)
    except OSError as error:
        print(f"cannot read file: {log_path}")
        return 1

    try:
        rules = parse_rules(read_text(rules_path))
    except (OSError, ValueError) as error:
        print(f"cannot read rules file: {rules_path}: {error}")
        return 1

    print(build_report(log_text, rules))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
