"""CLI for kdev-ingestor.

Usage:
    kdev-ingest inject --rules-dir <dir> --graph <path>
    kdev-ingest link --rules-dir <dir> --graph <path> --source-root <dir>
    kdev-ingest list-tags --graph <path>
    kdev-ingest spec-link-prepare --graph <path> --source-root <dir> --out <file> [--top-k N]
    kdev-ingest spec-link-finalize --graph <path> --verdicts <file> --source-root <dir> --report-dir <dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from ieidev_ingestor.graph_io import (
    GraphIOError,
    load_graph,
    save_graph,
    upsert_edge,
    upsert_node,
)
from ieidev_ingestor.security_rules import (
    RuleParseError,
    parse_rules_dir,
    rule_to_node,
)
from ieidev_ingestor.linkers.pattern_linker import PatternLinker
from ieidev_ingestor.linkers.semantic_linker_prepare import (
    prepare_intents,
    write_intents_json,
)
from ieidev_ingestor.linkers.semantic_linker_finalize import (
    finalize,
    render_report,
    write_report,
)


def _cmd_inject(args: argparse.Namespace) -> int:
    graph_path = Path(args.graph)
    rules_dir = Path(args.rules_dir)
    try:
        graph = load_graph(graph_path)
        rules = parse_rules_dir(rules_dir)
    except (GraphIOError, RuleParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    inserted = 0
    for rule in rules:
        node = rule_to_node(rule)
        upsert_node(graph, node)
        inserted += 1

    try:
        save_graph(graph, graph_path)
    except GraphIOError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"injected {inserted} rule node(s) into {graph_path}")
    return 0


def _cmd_list_tags(args: argparse.Namespace) -> int:
    try:
        graph = load_graph(Path(args.graph))
    except GraphIOError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    counter: Counter[str] = Counter()
    for node in graph.nodes:
        for tag in node.get("tags", []):
            if isinstance(tag, str) and tag.startswith("kdev:"):
                counter[tag] += 1

    for tag, count in sorted(counter.items()):
        print(f"{count:5d}  {tag}")
    return 0


def _cmd_link(args: argparse.Namespace) -> int:
    graph_path = Path(args.graph)
    source_root = Path(args.source_root)
    if not source_root.exists():
        print(f"error: source root not found: {source_root}", file=sys.stderr)
        return 2
    try:
        graph = load_graph(graph_path)
        rules = parse_rules_dir(Path(args.rules_dir))
    except (GraphIOError, RuleParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    edges = PatternLinker().link(rules, graph, source_root)
    linked = 0
    for edge in edges:
        try:
            upsert_edge(graph, edge)
            linked += 1
        except GraphIOError:
            continue

    try:
        save_graph(graph, graph_path)
    except GraphIOError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"linked {linked} security edge(s) into {graph_path}")
    return 0


def _cmd_spec_link_prepare(args: argparse.Namespace) -> int:
    graph_path = Path(args.graph)
    source_root = Path(args.source_root)
    out_path = Path(args.out)
    if not source_root.exists():
        print(f"error: source root not found: {source_root}", file=sys.stderr)
        return 2
    try:
        graph = load_graph(graph_path)
    except GraphIOError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    payload = prepare_intents(
        graph, str(graph_path), source_root, top_k=args.top_k
    )
    write_intents_json(payload, out_path)
    print(
        f"prepared {payload['intent_count']} intent(s) from "
        f"{payload['doc_count']} doc node(s) -> {out_path}"
    )
    return 0


def _cmd_spec_link_finalize(args: argparse.Namespace) -> int:
    graph_path = Path(args.graph)
    verdicts_path = Path(args.verdicts)
    source_root = Path(args.source_root)
    report_dir = Path(args.report_dir)
    try:
        graph = load_graph(graph_path)
    except GraphIOError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        verdicts_payload = json.loads(verdicts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read verdicts: {exc}", file=sys.stderr)
        return 2
    verdicts = verdicts_payload.get("verdicts", [])

    graph, report_data = finalize(graph, verdicts, source_root)
    try:
        save_graph(graph, graph_path)
    except GraphIOError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report_text = render_report(graph, report_data, source_root)
    report_path = write_report(report_text, report_dir)
    print(f"wrote {report_data['edges_written']} documents edge(s); "
          f"report -> {report_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kdev-ingest")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_inject = sub.add_parser("inject", help="inject security rules into a UA graph")
    p_inject.add_argument("--rules-dir", required=True)
    p_inject.add_argument("--graph", required=True)
    p_inject.set_defaults(func=_cmd_inject)

    p_list = sub.add_parser("list-tags", help="list kdev:* tags in a UA graph")
    p_list.add_argument("--graph", required=True)
    p_list.set_defaults(func=_cmd_list_tags)

    p_link = sub.add_parser("link", help="link security rules to code by pattern")
    p_link.add_argument("--rules-dir", required=True)
    p_link.add_argument("--graph", required=True)
    p_link.add_argument("--source-root", required=True)
    p_link.set_defaults(func=_cmd_link)

    p_prep = sub.add_parser(
        "spec-link-prepare",
        help="extract spec intents + candidates -> intents.json",
    )
    p_prep.add_argument("--graph", required=True)
    p_prep.add_argument("--source-root", required=True)
    p_prep.add_argument("--out", required=True)
    p_prep.add_argument("--top-k", type=int, default=30)
    p_prep.set_defaults(func=_cmd_spec_link_prepare)

    p_fin = sub.add_parser(
        "spec-link-finalize",
        help="apply verdicts to graph (upsert documents edges + report)",
    )
    p_fin.add_argument("--graph", required=True)
    p_fin.add_argument("--verdicts", required=True)
    p_fin.add_argument("--source-root", required=True)
    p_fin.add_argument("--report-dir", required=True)
    p_fin.set_defaults(func=_cmd_spec_link_finalize)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
