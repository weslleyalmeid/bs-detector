"""Print the compiled LangGraph as a Mermaid diagram.

Usage:
    python print_graph.py
or:
    make graph
"""

from pipeline import agents


def main() -> int:
    print(agents._graph.get_graph().draw_mermaid())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
