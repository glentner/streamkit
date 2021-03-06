# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Get variable from configuration file."""


# type annotations
from __future__ import annotations
from typing import Mapping, Any

# standard libs
import os
import functools
import logging

# internal libs
from ...core.config import SITE, CONF_PATH
from ...core.exceptions import log_exception

# external libs
from cmdkit.app import Application, exit_status
from cmdkit.cli import Interface
from cmdkit.config import Namespace, ConfigurationError
import toml


PROGRAM = f'streamkit config get'
USAGE = f"""\
usage: {PROGRAM} [-h] SECTION[...].VAR [--system | --user | --local]
{__doc__}\
"""

HELP = f"""\
{USAGE}

arguments:
SECTION[...].VAR          Path to variable.

options:
    --system              Load from system configuration.
    --user                Load from user configuration.
    --local               Load from local configuration.
-h, --help                Show this message and exit.\
"""


# initialize module level logger
log = logging.getLogger(__name__)


class GetConfigApp(Application):
    """Application class for config get command."""

    interface = Interface(PROGRAM, USAGE, HELP)

    varpath: str = None
    interface.add_argument('varpath', metavar='VAR')

    local: bool = False
    user: bool = False
    system: bool = False
    site_interface = interface.add_mutually_exclusive_group()
    site_interface.add_argument('--local', action='store_true')
    site_interface.add_argument('--user', action='store_true')
    site_interface.add_argument('--system', action='store_true')

    expand: bool = False
    interface.add_argument('-x', '--expand', action='store_true')

    exceptions = {
        RuntimeError: functools.partial(log_exception, log=log.critical,
                                        status=exit_status.runtime_error),
        ConfigurationError: functools.partial(log_exception, log=log.critical,
                                              status=exit_status.bad_config),
    }

    def run(self) -> None:
        """Business logic for `config get`."""

        config_path = CONF_PATH[SITE]
        for key in ('local', 'user', 'system'):
            if getattr(self, key) is True:
                config_path = CONF_PATH[key]

        if not os.path.exists(config_path):
            raise RuntimeError(f'{config_path} does not exist')

        config = Namespace.from_local(config_path)
        # with open(config_path, mode='r') as config_file:
        #     config = toml.load(config_file)

        if self.varpath == '.':
            self.print_result(config)
            return

        if '.' not in self.varpath:
            if self.varpath in config:
                self.print_result(config[self.varpath])
                return
            else:
                raise RuntimeError(f'"{self.varpath}" not found in {config_path}')

        if self.varpath.startswith('.'):
            raise RuntimeError(f'section name cannot start with "."')

        section, *subsections, variable = self.varpath.split('.')
        if section not in config:
            raise RuntimeError(f'"{section}" is not a section')

        config_section = config[section]
        if subsections:
            subpath = f'{section}'
            try:
                for subsection in subsections:
                    subpath += f'.{subsection}'
                    if not isinstance(config_section[subsection], Mapping):
                        raise RuntimeError(f'"{subpath}" not a section in {config_path}')
                    else:
                        config_section = config_section[subsection]
            except KeyError as error:
                raise RuntimeError(f'"{subpath}" not found in {config_path}') from error

        if self.expand:
            try:
                value = getattr(config_section, variable)
            except ValueError as error:
                raise RuntimeError(*error.args) from error
            if value is None:
                raise RuntimeError(f'"{variable}" not found in {config_path}')
            self.print_result(value)
            return

        if variable not in config_section:
            raise RuntimeError(f'"{self.varpath}" not found in {config_path}')

        self.print_result(config_section[variable])

    def print_result(self, value: Any) -> None:
        """Print the final result."""
        if isinstance(value, Mapping):
            if self.varpath == '.':
                value = toml.dumps(value)
            else:
                value = toml.dumps({self.varpath: value})
            lines = []
            for line in value.strip().split('\n'):
                if not line.startswith('['):
                    lines.append(line)
                else:
                    lines.append(line.replace('"', ''))
            value = '\n'.join(lines)
        print(value, flush=True)
