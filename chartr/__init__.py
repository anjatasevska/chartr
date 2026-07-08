# Register PyMySQL as the MySQLdb driver when it's available (local MySQL dev).
# On Postgres-only environments (e.g. Render) pymysql isn't installed, so skip it.
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:
    pass
