from peewee import (
    Model, IntegerField, CharField,
    DateTimeField, ForeignKeyField
)
from datetime import datetime
from database import db


class BaseModel(Model):
    class Meta:
        database = db


class Medicine(BaseModel):
    name  = CharField(max_length=150)
    price = IntegerField()
    stock = IntegerField(default=0)

    class Meta:
        table_name = "medicines"


class Sale(BaseModel):
    medicine = ForeignKeyField(Medicine, backref="sales", on_delete="CASCADE")
    quantity = IntegerField()
    total    = IntegerField()
    sold_at  = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "sales"