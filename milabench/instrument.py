import time

from .bench import StopProgram


class Plain:
    def __init__(self, x):
        self._object = x

    def __rich__(self):
        return self._object


def dash(runner, gv):
    """Create a simple terminal dashboard using rich.
    This displays a live table of the last value for everything given,
    with a progress bar for the current task under it.
    """

    from rich.console import Group
    from rich.live import Live
    from rich.pretty import Pretty
    from rich.progress import Progress
    from rich.table import Table

    # Current rows are stored here
    rows = {}

    # First, a table with the latest value of everything that was given
    table = Table.grid(padding=(0, 3, 0, 0))
    table.add_column("key", style="bold green")
    table.add_column("value")

    # Below, a progress bar for the current task (train or test)
    progress_bar = Progress(auto_refresh=False)
    current_task = progress_bar.add_task("----")

    # Group them
    grp = Group(table, progress_bar)

    # This will wrap Live around the run block (the whole main function)
    gv.wrap("run", Live(grp, refresh_per_second=4))

    # This sets the progress bar's completion meter
    @gv.where("progress").ksubscribe
    def _(progress, total, descr):
        progress_bar.reset(current_task, total=total, description=descr)
        progress_bar.update(current_task, completed=progress)

    # This updates the table every time we get new values
    @gv.where("!silent").subscribe
    def _(values):
        for k, v in values.items():
            if k.startswith("$") or k.startswith("#"):
                continue
            if k in rows:
                rows[k]._object = v
            else:
                if isinstance(v, str):
                    rows[k] = Plain(v)
                else:
                    rows[k] = Pretty(v)
                table.add_row(k, rows[k])


def stop(runner, gv):
    n = runner.config.niters
    gv["?metric"].count(scan=True).map(
        lambda x: dict(progress=x, total=n, descr="Progress", silent=True)
    ).give()
    gv["?metric"].skip(n).fail(exc_type=StopProgram)


def timings(runner, gv):
    times = (
        gv["?metric"]
        .map(lambda _: time.time())
        .pairwise()
        .starmap(lambda x, y: 1000 * (y - x))
    )

    reports = {
        "min duration": times.min(scan=True),
        "avg duration": times.average(scan=10),
        "max duration": times.max(scan=True),
    }

    for name, stream in reports.items():
        stream.format("{:3.2f}ms").give(name)


def dump(runner, gv):
    gv.display()


def wandb(runner, gv):
    import wandb

    entity, project = runner.config.wandb.split(":")

    @gv["?args"].subscribe
    def _(args):
        wandb.init(project=project, entity=entity, config=vars(args))
        gv["?model"].first() >> wandb.watch
        gv.keep("metric") >> wandb.log
