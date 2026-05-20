"""
Demo server launcher

Entry point for the `mypromotion-engine-demo` CLI command.
"""


def main():
    try:
        from demo.app import main as _main
    except ImportError:
        raise ImportError(
            "Demo dependencies not installed. "
            "Run: pip install mypromotion-engine-core[demo]"
        )
    _main()
