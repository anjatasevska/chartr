#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


class _SafeStream:
    """Wrap a text stream so console writes never crash the app.

    On Windows the default console encoding (cp1252) raises
    UnicodeEncodeError on emoji, and redirected pipes can raise
    OSError. Both would otherwise turn debug ``print()`` calls into
    500 errors. This wrapper degrades gracefully to ASCII instead.
    """

    def __init__(self, stream):
        self._stream = stream

    def write(self, data):
        try:
            return self._stream.write(data)
        except (UnicodeEncodeError, OSError, ValueError):
            try:
                safe = data.encode("ascii", "replace").decode("ascii")
                return self._stream.write(safe)
            except Exception:
                return len(data)

    def flush(self):
        try:
            return self._stream.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._stream, name)


sys.stdout = _SafeStream(sys.stdout)
sys.stderr = _SafeStream(sys.stderr)


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chartr.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
