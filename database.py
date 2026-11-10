from peewee import SqliteDatabase

db = SqliteDatabase("pharmacy.db")


def init_db() -> None:
    """اتصال + ساخت جدول‌ها"""
    db.connect(reuse_if_open=True)
    from models import Medicine, Sale
    db.create_tables([Medicine, Sale])