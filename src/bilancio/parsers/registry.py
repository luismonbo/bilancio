"""Parser registry — the list of all known BankParser implementations.

Adding a new bank: import its parser here and add an instance to the list.
"""

from bilancio.parsers.base import BankParser
from bilancio.parsers.mediobanca_premier import MediobancaPremierParser


def default_parsers() -> list[BankParser]:
    """Return a fresh list of all registered bank parsers.

    Called once per ImportService construction when no explicit parser list
    is provided.  Kept as a factory (not a module-level constant) so each
    service instance gets independent objects and tests can inject fakes.
    """
    return [MediobancaPremierParser()]  # type: ignore[list-item]
