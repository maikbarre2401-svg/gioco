#!/usr/bin/env python3
"""CLI operativo di Frank: task, bug e stato.

Esempi:
    python3 .claude/frank_cli.py status
    python3 .claude/frank_cli.py task open "scrivere il parser"
    python3 .claude/frank_cli.py task close
    python3 .claude/frank_cli.py bug add "crash su input vuoto"
    python3 .claude/frank_cli.py bug resolve 0
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import frank_core as core


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="frank", description="CLI di Frank")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="mostra lo stato corrente")
    sub.add_parser("wake", help="messaggio di risveglio")
    sub.add_parser("remember", help="persiste lo stato (fine sessione)")

    task = sub.add_parser("task", help="gestisci il task corrente")
    task_sub = task.add_subparsers(dest="action", required=True)
    task_open = task_sub.add_parser("open", help="apri un task")
    task_open.add_argument("desc", help="descrizione del task")
    task_sub.add_parser("close", help="chiudi il task corrente")

    bug = sub.add_parser("bug", help="gestisci i bug noti")
    bug_sub = bug.add_subparsers(dest="action", required=True)
    bug_add = bug_sub.add_parser("add", help="registra un bug")
    bug_add.add_argument("desc", help="descrizione del bug")
    bug_res = bug_sub.add_parser("resolve", help="risolvi un bug per indice")
    bug_res.add_argument("index", type=int, help="indice del bug (vedi status)")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.cmd == "wake":
        print(core.wake())
        return 0
    if args.cmd == "remember":
        core.remember()
        print("[FRANK] stato persistito.")
        return 0
    if args.cmd == "status":
        print(core.status())
        return 0

    if args.cmd == "task":
        if args.action == "open":
            core.open_task(args.desc)
            print(f"[FRANK] task aperto: {args.desc}")
        else:
            core.close_task()
            print("[FRANK] task chiuso.")
    elif args.cmd == "bug":
        if args.action == "add":
            core.add_bug(args.desc)
            print(f"[FRANK] bug registrato: {args.desc}")
        else:
            core.resolve_bug(args.index)
            print(f"[FRANK] bug #{args.index} risolto.")

    print(core.status())
    return 0


if __name__ == "__main__":
    sys.exit(main())
