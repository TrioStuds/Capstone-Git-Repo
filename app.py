from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:password@localhost/vpn_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'vpn_secret_key'\

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)

    banks = db.relationship('BankInfo', backref='user', lazy=True)
    portfolio = db.relationship('Portfolio', back_populates='user', lazy=True)
    orders = db.relationship('OrderHistory', back_populates='user', lazy=True)
    transactions = db.relationship('FinancialTransaction', back_populates='user', lazy=True)

    def __repr__(self):
        return f"<User {self.email}>"

class BankInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    institute_name = db.Column(db.String(100))
    routing_number = db.Column(db.String(20))
    account_number = db.Column(db.String(20))

    def __repr__(self):
        return f"<User {User.email}"
    
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    industry = db.Column(db.String(100))

    stocks = db.relationship('StockInventory', back_populates='company', lazy=True)

    def __repr__(self):
        return f"<Company {self.name}>"
        
class StockMarket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(50), nullable=False)

    stocks = db.relationship('StockInventory', back_populates='market', lazy=True)

    def __repr__(self):
        return f"<StockMarket {self.name}>"
    
class StockInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker_symbol = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)

    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    market_id = db.Column(db.Integer, db.ForeignKey('stock_market.id'), nullable=False)

    company = db.relationship('Company', back_populates='stocks')
    market = db.relationship('StockMarket', back_populates='stocks')
    portfolio_entries = db.relationship('Portfolio', back_populates='stock', lazy=True)

    def __repr__(self):
        return f"<Stock {self.ticker_symbol}>"
    
class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock_inventory.id'), nullable=False)

    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    avg_purchase_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    user = db.relationship('User', back_populates='portfolio')
    stock = db.relationship('StockInventory', back_populates='portfolio_entries')

    def __repr__(self):
        return f"<Portfolio Stock={self.stock_id} Qty={self.quantity}>"
    
class OrderHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock_inventory.id'), nullable=False)

    order_type = db.Column(db.Enum('BUY', 'SELL', name='order_type_enum'), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    total_cost = db.Column(db.Numeric(12, 2), nullable=False)  # quantity * price
    order_date = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='orders')
    stock = db.relationship('StockInventory')

    def __repr__(self):
        return f"<Order {self.order_type} {self.quantity} {self.stock.ticker_symbol}>"

class FinancialTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    amount = db.Column(db.Numeric(12, 2), nullable=False)
    transaction_type = db.Column(
        db.Enum('DEPOSIT', 'WITHDRAWAL', 'FEE', 'DIVIDEND', name='transaction_type_enum'),
        nullable=False
    )
    related_order_id = db.Column(db.Integer, db.ForeignKey('order_history.id'), nullable=True)  
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='transactions')
    related_order = db.relationship('OrderHistory')

    def __repr__(self):
        return f"<Transaction {self.transaction_type} {self.amount}>"
    
class Administrator(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Administrator {self.email}>"

with app.app_context():
    db.create_all()

    if not Administrator.query.filter_by(email="admin@email.com").first():
        admin_user = Administrator(
            email="admin@email.com",
            password="password"
        )
        db.session.add(admin_user)
        db.session.commit()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email, password=password).first()
        admin = Administrator.query.filter_by(email=email, password=password).first()

        if user:
            return redirect(url_for('customer_home'))
        elif admin:
            return redirect(url_for('admin_home'))
        else:
            flash('Invalid email or password', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/customer_home')
def customer_home():
    return render_template('customer_home.html')

@app.route('/admin_home')
def admin_home():
    return render_template('admin_home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        bank_institute_name = request.form.get('bank_institute_name')
        bank_routing_number = request.form.get('bank_routing_number')
        bank_account_number = request.form.get('bank_account_number')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered!", "danger")
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('register'))

        new_user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password
        )
        db.session.add(new_user)
        db.session.commit()

        if bank_institute_name or bank_routing_number or bank_account_number:
            new_bank = BankInfo(
                user_id=new_user.id,
                institute_name=bank_institute_name,
                routing_number=bank_routing_number,
                account_number=bank_account_number
            )
            db.session.add(new_bank)
            db.session.commit()

        flash("Account created successfully!", "success")
        return redirect(url_for('customer_home'))

    return render_template('register.html')

if __name__ == '__main__':
    app.run(debug=True)