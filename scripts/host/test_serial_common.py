#!/usr/bin/env python3
"""Regression checks for the shared Host serial policy and redaction."""

from serial_common import DEFAULT_BAUD, DEFAULT_PORT, redact, open_port
from unittest.mock import patch


def main() -> None:
    class FakeSerial:
        def __init__(self, port, baudrate, timeout):
            assert port is None and baudrate == DEFAULT_BAUD
            self.dtr = self.rts = True
        def open(self):
            assert self.port == DEFAULT_PORT
            assert self.dtr is False and self.rts is False
    with patch("serial_common.serial.Serial", FakeSerial):
        open_port()
    source = "\n".join((
        "@join Pura80pro+ 12345678",
        "@join \"Pura80pro+\" \"12345678\"",
        "@mimo-set sk-secret",
        'AT+CWJAP="Pura80pro+","12345678"',
    ))
    redacted = redact(source)

    assert DEFAULT_PORT == "COM7"
    assert DEFAULT_BAUD == 1_000_000
    for secret in ("Pura80pro+", "12345678", "sk-secret"):
        assert secret not in redacted
    assert redacted.count("<redacted>") == 3
    assert "AT+CWJAP=***" in redacted
    print("PASS: serial defaults and log redaction")


if __name__ == "__main__":
    main()
