from sqlalchemy import Column, String, Integer, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from werkzeug.security import generate_password_hash, check_password_hash

class Order(Base):
    __tablename__ = "orders"

    user_id = Column(String(10), primary_key=True)
    order_type = Column(String(20))
    location = Column(String(100))
    payment = Column(String(20))
    
    containers = relationship("Container", back_populates="order")

class Container(Base):
    __tablename__ = "containers"

    container_id = Column(Integer, primary_key=True)
    order_id = Column(String(10), ForeignKey("orders.user_id"))
    container_number = Column(Integer)
    packaging_type = Column(String(50))
    message = Column(String)
    
    order = relationship("Order", back_populates="containers")
    food_items = relationship("FoodItem", back_populates="container")

class FoodItem(Base):
    __tablename__ = "food_items"

    item_id = Column(Integer, primary_key=True)
    container_id = Column(Integer, ForeignKey("containers.container_id"))
    food_name = Column(String(100))
    price = Column(Numeric(10, 2))
    
    container = relationship("Container", back_populates="food_items")

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)