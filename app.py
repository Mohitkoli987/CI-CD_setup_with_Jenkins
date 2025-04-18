from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql
import os
from flask import send_from_directory
from werkzeug.utils import secure_filename
from sklearn.neighbors import NearestNeighbors
import pandas as pd
# import openai
from dotenv import load_dotenv
import google.generativeai as genai
import requests

# Load .env variables
load_dotenv()
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# GEMINI_MODEL = "gemini-1.5-flash"  # Or "gemini-1.5-pro" based on your needs
# GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

genai.configure(api_key=GEMINI_API_KEY)
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'



# MySQL Configuration
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '12345678'
app.config['MYSQL_DB'] = 'ecom1'


UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Custom MySQL Wrapper
class MySQL:
    def __init__(self, app):
        self.app = app

    @property
    def connection(self):
        return pymysql.connect(
            host=self.app.config['MYSQL_HOST'],
            user=self.app.config['MYSQL_USER'],
            password=self.app.config['MYSQL_PASSWORD'],
            database=self.app.config['MYSQL_DB'],
            cursorclass=pymysql.cursors.DictCursor
        )

mysql = MySQL(app)



# Static folder for serving images
@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone = request.form['phone']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('register'))

        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, first_name, last_name, phone, password) VALUES (%s, %s, %s, %s, %s)",
                       (username, first_name, last_name, phone, password))
        conn.commit()
        cursor.close()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        cursor.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('home'))
        else:
            flash("Invalid credentials!", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/base')
def base():
    return render_template('base.html')

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        category = request.form['category']
        price = request.form['price']  # Get price from form

        # Handle Image Upload
        image = request.files['image']
        if image and image.filename != '':
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)  # Save image to uploads folder
        else:
            filename = None  # No image uploaded

        # Insert Product into Database
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute("INSERT INTO products (name, description, category, price, image) VALUES (%s, %s, %s, %s, %s)",
                           (name, description, category, price, filename))
            conn.commit()
            flash('Product added successfully!', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'danger')
        finally:
            cursor.close()

        return redirect(url_for('home'))

    return render_template('add_product.html')



@app.route('/order/<int:product_id>')
def order_product(product_id):
    if 'user_id' not in session:
        flash('Please log in to place an order.', 'warning')
        return redirect(url_for('login'))

    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (user_id, product_id) VALUES (%s, %s)", (session['user_id'], product_id))
    conn.commit()
    cursor.close()

    flash('Order placed successfully!', 'success')
    return redirect(url_for('profile'))

@app.route('/', methods=['GET', 'POST'])
def home():
    search_query = request.args.get('search', '').strip()
    conn = mysql.connection
    cursor = conn.cursor()

    # 🔹 Default: Latest Products
    cursor.execute("SELECT id, name, description, category, price, image FROM products ORDER BY id DESC LIMIT 5")
    recommended_products = cursor.fetchall()

    user_id = session.get('user_id')  # Check if user is logged in
    if user_id:
        # 🔹 Check if user has any past orders
        cursor.execute("SELECT COUNT(*) AS order_count FROM orders WHERE user_id = %s", (user_id,))
        order_count = cursor.fetchone()['order_count']

        if order_count > 0:  # If user has orders, recommend products based on past orders
            cursor.execute("""
                SELECT p.id, p.name, p.description, p.category, p.price, p.image, o.order_date
                FROM products p
                JOIN orders o ON p.category = (
                    SELECT category FROM products WHERE id = o.product_id LIMIT 1
                )
                WHERE o.user_id = %s 
                ORDER BY o.order_date DESC 
                LIMIT 5
            """, (user_id,))
            recommended_products = cursor.fetchall()

    # 🔹 Fetch Products Based on Search or All Products
    if search_query:
        cursor.execute("""
            SELECT id, name, description, category, price, image 
            FROM products 
            WHERE LOWER(name) LIKE LOWER(%s) 
               OR LOWER(category) LIKE LOWER(%s)
               OR LOWER(description) LIKE LOWER(%s)
        """, (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"))
    else:
        cursor.execute("SELECT id, name, description, category, price, image FROM products")

    products = cursor.fetchall()
    cursor.close()

    # 🔹 Group Products by Category
    categorized_products = {}
    for product in products:
        category = product['category']
        if category not in categorized_products:
            categorized_products[category] = []
        categorized_products[category].append(product)

    return render_template('home.html', 
                           categorized_products=categorized_products, 
                           recommended_products=recommended_products, 
                           search_query=search_query)




@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = mysql.connection
    cursor = conn.cursor()

    # Fetch user details
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    # Fetch user orders with product details
    cursor.execute("""
        SELECT products.name, products.image, products.description, products.price, orders.order_date
        FROM orders
        JOIN products ON orders.product_id = products.id
        WHERE orders.user_id = %s
        ORDER BY orders.order_date DESC
    """, (user_id,))
    orders = cursor.fetchall()

    # Fetch wishlist products
    cursor.execute("""
        SELECT products.id, products.name, products.image, products.description, products.price 
        FROM wishlist
        JOIN products ON wishlist.product_id = products.id
        WHERE wishlist.user_id = %s
    """, (user_id,))
    wishlist_items = cursor.fetchall()

    cursor.close()
    
    return render_template('profile.html', user=user, orders=orders, wishlist_items=wishlist_items)


def get_product_data():
    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, category FROM products")
    data = cursor.fetchall()
    cursor.close()
    return pd.DataFrame(data)

def train_knn():
    df = get_product_data()
    model = NearestNeighbors(n_neighbors=3, algorithm="auto")
    model.fit(df[['price']])  # We use price as a feature; can be expanded
    return model, df

knn_model, product_df = train_knn()

@app.route("/recommend/<int:product_id>")
def recommend(product_id):
    product_idx = product_df[product_df["id"] == product_id].index[0]
    distances, indices = knn_model.kneighbors([product_df.iloc[product_idx][['price']]])

    recommended_products = product_df.iloc[indices[0]].to_dict(orient="records")
    return render_template("recommendations.html", products=recommended_products)


@app.route('/wishlist/<int:product_id>', methods=['POST'])
def toggle_wishlist(product_id):
    if "user_id" not in session:
        return jsonify({"login_required": True})  # Redirect to login if not logged in

    user_id = session["user_id"]
    conn = mysql.connection
    cursor = conn.cursor()

    # Check if product is already in the wishlist
    cursor.execute("SELECT id FROM wishlist WHERE user_id = %s AND product_id = %s", (user_id, product_id))
    existing = cursor.fetchone()

    if existing:
        # Remove from wishlist
        cursor.execute("DELETE FROM wishlist WHERE user_id = %s AND product_id = %s", (user_id, product_id))
        conn.commit()
        cursor.close()
        return jsonify({"status": "removed"})
    else:
        # Add to wishlist
        cursor.execute("INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)", (user_id, product_id))
        conn.commit()
        cursor.close()
        return jsonify({"status": "added"})




if __name__ == '__main__':
    app.run(debug=True)
