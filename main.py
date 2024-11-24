from database import Base, engine
from models import Order, Container, FoodItem, User

Base.metadata.create_all(bind=engine)