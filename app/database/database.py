from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

_engine = None
_sessionmaker = None


def init_engine(database_url: str):
    global _engine, _sessionmaker

    # already initialized (e.g. overridden in tests)
    if _engine is not None:
        return

    _engine = create_async_engine(
        database_url,
        connect_args={"statement_cache_size": 0},
    )

    _sessionmaker = async_sessionmaker(
        bind=_engine,
        expire_on_commit=False
    )


def get_sessionmaker():
    if _sessionmaker is None:
        raise RuntimeError("DB not initialized. Call init_engine() first.")
    return _sessionmaker


def override_engine(engine):
    global _engine, _sessionmaker
    _engine = engine
    _sessionmaker = async_sessionmaker(
        bind=engine,
        expire_on_commit=False
    )
