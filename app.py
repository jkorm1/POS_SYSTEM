from flask import Flask, request, jsonify
from flask_cors import CORS
from database import SessionLocal
from models import Order, Container, FoodItem, User
from sqlalchemy.orm import joinedload
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime

app = Flask(__name__)
CORS(app)

# Add this secret key configuration
app.config['SECRET_KEY'] = 'your-secret-key-keep-it-secret'  # Change this in production

@app.route('/cards', methods=['GET'])
def get_cards():
    session = SessionLocal()
    
    # Get all orders with their related containers and food items
    orders = session.query(Order).options(
        joinedload(Order.containers).joinedload(Container.food_items)
    ).all()
    
    result = []
    for order in orders:
        order_data = {
            "user_id": order.user_id,
            "order_type": order.order_type,
            "location": order.location,
            "Payment": order.payment,
            "containers": {}
        }
        
        # Transform containers and food items into the expected format
        for container in order.containers:
            container_data = {
                "PackagingType": container.packaging_type,
                "message": container.message or "",
                "FoodItems": [
                    {
                        "Food": item.food_name,
                        "Price": f"{float(item.price):.2f}"
                    }
                    for item in container.food_items
                ]
            }
            
            # Use container_id as the key in containers object
            order_data["containers"][str(container.container_id)] = container_data
        
        result.append(order_data)
    
    session.close()
    return jsonify(result)

@app.route('/auth/signup', methods=['POST', 'OPTIONS'])
def signup():
    if request.method == 'OPTIONS':
        return '', 204
    
    data = request.get_json()
    
    # Validate input data
    if not all(k in data for k in ['username', 'email', 'password']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    session = SessionLocal()
    try:
        # Check if user already exists
        if session.query(User).filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already taken'}), 400
        if session.query(User).filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        # Create new user
        new_user = User(
            username=data['username'],
            email=data['email']
        )
        new_user.set_password(data['password'])
        
        session.add(new_user)
        session.commit()
        
        return jsonify({'message': 'Registration successful'}), 201
    
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/auth/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return '', 204
    
    data = request.get_json()
    
    if not all(k in data for k in ['username', 'password']):
        return jsonify({'error': 'Missing username or password'}), 400
    
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=data['username']).first()
        
        if user and user.check_password(data['password']):
            # Generate token
            token = jwt.encode({
                'user_id': user.id,
                'username': user.username,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            }, app.config['SECRET_KEY'])
            
            return jsonify({
                'token': token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            })
        
        return jsonify({'error': 'Invalid username or password'}), 401
    
    finally:
        session.close()

# Optional: Add a token verification endpoint
@app.route('/auth/verify', methods=['GET'])
def verify_token():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'error': 'No token provided'}), 401
    
    try:
        # Remove 'Bearer ' from token
        token = token.split(' ')[1]
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return jsonify({'valid': True, 'user': payload}), 200
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401

@app.route('/users', methods=['GET'])
def get_users():
    session = SessionLocal()
    try:
        users = session.query(User).all()
        result = [
            {
                "id": user.id,
                "username": user.username,
                "email": user.email
            }
            for user in users
        ]
        return jsonify(result)
    finally:
        session.close()

if __name__ == '__main__':
    app.run(debug=True)