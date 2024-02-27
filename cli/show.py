import click


@click.command()
def openconfig_cli_example():
    """ This is an openconfig-cli example command """

    click.echo("Hello from openconfig-cli example")


def register(cli):
    cli.add_command(openconfig_cli_example)
