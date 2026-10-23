"""Plain: write steps in everyday English, then run them."""

__version__ = "0.1.0"


def check(source, **kwargs):
    """Read a program without running it. Returns the Program; its .problems lists anything to fix."""
    from .parser import Reader
    return Reader(**kwargs).read(source)


def run(source, host):
    """Read and run a program with the given host. Returns (program, problem or None)."""
    from .interpreter import Run
    from .problems import Problem
    program = check(source)
    if program.problems:
        return program, program.problems[0]
    try:
        Run(program, host).run()
    except Problem as problem:
        return program, problem
    return program, None
