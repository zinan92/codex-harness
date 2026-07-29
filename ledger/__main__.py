"""Command dispatcher for the local usage ledger."""

import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m ledger")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("collect", help="collect normalized local usage records")
    subcommands.add_parser("report", help="report local costs by project")
    args, remaining = parser.parse_known_args(argv)
    if args.command == "collect":
        from .collect import main as collect_main
        return collect_main(remaining)
    from .report import main as report_main
    return report_main(remaining)


if __name__ == "__main__":
    main()
