from flask import Flask, request, jsonify
from flask_cors import CORS
from database import conn
import psycopg2
from psycopg2.extras import RealDictCursor
import secrets
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})
app.config['SECRET_KEY'] = 'your-secret-key'

@app.route('/api/menu-items', methods=['GET', 'POST'])
def menu_items():
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'GET':
        try:
            cursor.execute("""
                SELECT f.item_id, f.food_name, f.price, c.packaging_type 
                FROM food_items f 
                JOIN containers c ON f.container_id = c.container_id
                ORDER BY f.food_name
            """)
            items = cursor.fetchall()
            return jsonify(items)
            
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
            
        finally:
            cursor.close()

    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['food_name', 'price', 'packaging_type']
            if not all(field in data for field in required_fields):
                return jsonify({"error": "Missing required fields"}), 400

            # Validate price is a positive number
            try:
                price = float(data['price'])
                if price < 0:
                    raise ValueError
            except ValueError:
                return jsonify({"error": "Invalid price"}), 400

            # Start transaction
            cursor.execute("BEGIN")

            # Create new container
            cursor.execute(
                "INSERT INTO containers (packaging_type) VALUES (%s) RETURNING container_id",
                (data['packaging_type'],)
            )
            container_id = cursor.fetchone()['container_id']

            # Create food item
            cursor.execute("""
                INSERT INTO food_items (container_id, food_name, price)
                VALUES (%s, %s, %s)
                RETURNING item_id, food_name, price
            """, (container_id, data['food_name'], price))
            
            new_item = cursor.fetchone()
            
            # Commit transaction
            conn.commit()
            
            return jsonify({
                "message": "Menu item added successfully",
                "item": new_item
            }), 201

        except psycopg2.Error as e:
            conn.rollback()
            return jsonify({"error": f"Database error: {str(e)}"}), 500
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            cursor.close()

@app.route('/api/menu-items/<int:item_id>', methods=['DELETE'])
def delete_menu_item(item_id):
    cursor = conn.cursor()
    try:
        # Start transaction
        cursor.execute("BEGIN")
        
        # Get container_id first
        cursor.execute(
            "SELECT container_id FROM food_items WHERE item_id = %s",
            (item_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            return jsonify({"error": "Item not found"}), 404
            
        container_id = result[0]
        
        # Delete food item
        cursor.execute("DELETE FROM food_items WHERE item_id = %s", (item_id,))
        
        # Delete associated container
        cursor.execute("DELETE FROM containers WHERE container_id = %s", (container_id,))
        
        # Commit transaction
        conn.commit()
        
        return jsonify({"message": "Menu item deleted successfully"}), 200
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
        
    finally:
        cursor.close()

@app.route('/api/orders', methods=['GET'])
def get_orders():
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT o.*, 
                   json_object_agg(
                       c.container_id,
                       json_build_object(
                           'container_number', c.container_number,
                           'packaging_type', c.packaging_type,
                           'message', c.message,
                           'FoodItems', (
                               SELECT json_agg(
                                   json_build_object(
                                       'food_name', f.food_name,
                                       'Price', f.price
                                   )
                               )
                               FROM food_items f
                               WHERE f.container_id = c.container_id
                           )
                       )
                   ) as containers
            FROM orders o
            JOIN containers c ON o.user_id = c.order_id
            WHERE o.payment = 'pending' 
            AND o.order_type = 'customer_online'
            GROUP BY o.user_id, o.order_type, o.location, o.payment
        """)
        orders = cursor.fetchall()
        return jsonify(orders)
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500
            
    finally:
        cursor.close()

@app.route('/api/submit-order', methods=['POST'])
def submit_order():
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        data = request.get_json()
        
        # Generate unique order ID
        order_id = f"CUST_{secrets.token_hex(4).upper()}"
        
        # Start transaction
        cursor.execute("BEGIN")
        
        # Create order
        cursor.execute("""
            INSERT INTO orders (user_id, order_type, location, payment)
            VALUES (%s, %s, %s, %s)
            RETURNING user_id
        """, (order_id, data['order_type'], data['location'], data['payment']))
        
        # Process containers and food items
        for container in data['containers']:
            cursor.execute("""
                INSERT INTO containers (order_id, container_number, packaging_type, message)
                VALUES (%s, %s, %s, %s)
                RETURNING container_id
            """, (order_id, container['container_number'], 
                 container['packaging_type'], container['message']))
            
            container_id = cursor.fetchone()['container_id']
            
            # Add food items to container
            for item in container['FoodItems']:
                cursor.execute("""
                    INSERT INTO food_items (container_id, food_name, price)
                    VALUES (%s, %s, %s)
                """, (container_id, item['food_name'], item['Price']))
        
        conn.commit()
        return jsonify({"message": "Order submitted successfully", "order_id": order_id}), 201
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
        
    finally:
        cursor.close()

@app.route('/auth/login', methods=['POST'])
def login():
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        print(f"Login attempt for user: {username}")
        print(f"Password received: {password}")  # Debug print

        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if not user:
            print(f"No user found with username: {username}")
            return jsonify({'error': 'Invalid credentials'}), 401

        print(f"Found user: {user['username']}")
        print(f"Stored hash: {user['password_hash'][:50]}...")

        # Try password verificationy
        is_valid = check_password_hash(user['password_hash'], password)
        print(f"Password verification result: {is_valid}")

        if is_valid:
            token = jwt.encode({
                'user_id': user['id'],
                'username': user['username'],
                'exp': datetime.utcnow() + timedelta(hours=24)
            }, app.config['SECRET_KEY'])

            return jsonify({
                'token': token,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email']
                }
            }), 200
        else:
            print("Password verification failed")
            return jsonify({'error': 'Invalid credentials'}), 401

    except Exception as e:
        print(f"Login error details: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

@app.route('/auth/verify', methods=['GET'])
def verify_token():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'message': 'Token is missing'}), 401

    try:
        token = token.split(' ')[1]  # Remove 'Bearer ' prefix
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return jsonify({
            'user': {
                'username': data['username']
            }
        }), 200
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid token'}), 401

@app.route('/cards', methods=['GET'])
def get_cards():
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT o.*, 
                   json_object_agg(
                       c.container_id,
                       json_build_object(
                           'container_number', c.container_number,
                           'packaging_type', c.packaging_type,
                           'message', c.message,
                           'FoodItems', (
                               SELECT json_agg(
                                   json_build_object(
                                       'food_name', f.food_name,
                                       'Price', f.price
                                   )
                               )
                               FROM food_items f
                               WHERE f.container_id = c.container_id
                           )
                       )
                   ) as containers
            FROM orders o
            JOIN containers c ON o.user_id = c.order_id
            WHERE o.payment = 'pending' 
            GROUP BY o.user_id, o.order_type, o.location, o.payment
        """)
        orders = cursor.fetchall()
        return jsonify(orders)
            
    except Exception as e:
        print(f"Error fetching cards: {str(e)}")  # Debug print
        return jsonify({"error": str(e)}), 500
            
    finally:
        cursor.close()

@app.route('/auth/signup', methods=['POST'])
def signup():
    cursor = conn.cursor()
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')

        print(f"Attempting signup with data: {username}, {email}")  # Debug print

        # Check if username exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify({'error': 'Username already exists'}), 400

        # Hash password
        password_hash = generate_password_hash(password)

        # Insert user
        cursor.execute("""
            INSERT INTO users (username, email, password_hash)
            VALUES (%s, %s, %s)
            RETURNING id, username, email
        """, (username, email, password_hash))
        
        user_id, username, email = cursor.fetchone()
        conn.commit()

        # Generate token
        token = jwt.encode({
            'user_id': user_id,
            'username': username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'])

        return jsonify({
            'token': token,
            'user': {
                'id': user_id,
                'username': username,
                'email': email
            }
        }), 201

    except Exception as e:
        print(f"Signup error: {str(e)}")  # Debug print
        import traceback
        print(traceback.format_exc())  # Print full stack trace
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

if __name__ == '__main__':
    app.run(debug=True)