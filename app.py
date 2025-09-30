from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from decimal import Decimal
from datetime import datetime, timedelta

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:password@localhost/vpn_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'vpn_secret_key'

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    cash = db.Column(db.Numeric(12, 2), nullable=False, default=0)

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
    routing_number = db.Column(db.Integer())
    account_number = db.Column(db.Integer())

    def __repr__(self):
        if self.user:
            return f"<BankInfo id={self.id} user_email={self.user.email}>"
        return f"<BankInfo id={self.id} user_id={self.user_id}>"
    
class StockMarket(db.Model):
    id = db.Column(db.Integer, primary_key=True) 
    ticker_symbol = db.Column(db.String(4), unique=True, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    company_name = db.Column(db.String(150), nullable=False)
    industry = db.Column(db.String(100))
    country = db.Column(db.String(50), nullable=False)

    portfolio_entries = db.relationship('Portfolio', back_populates='stock', lazy=True)

    def __repr__(self):
        return f"<Stock {self.ticker_symbol} ({self.company_name})>"
    
class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock_market.id'), nullable=False)

    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    avg_purchase_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    user = db.relationship('User', back_populates='portfolio')
    stock = db.relationship('StockMarket', back_populates='portfolio_entries')

    def __repr__(self):
        return f"<Portfolio Stock={self.stock_id} Qty={self.quantity}>"
    
class OrderHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock_market.id'), nullable=False)

    order_type = db.Column(db.Enum('BUY', 'SELL', name='order_type_enum'), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    total_cost = db.Column(db.Numeric(12, 2), nullable=False)
    order_placed_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed = db.Column(db.Boolean, default=False)

    user = db.relationship('User', back_populates='orders')
    stock = db.relationship('StockMarket')

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
    
class MarketHours(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    market_id = db.Column(db.Integer, db.ForeignKey('stock_market.id'), nullable=False)
    open_time = db.Column(db.Time, nullable=False)
    close_time = db.Column(db.Time, nullable=False)

    def __repr__(self):
        return f"<MarketHours {self.market.name} {self.open_time}-{self.close_time}>"

class MarketSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    market_id = db.Column(db.Integer, db.ForeignKey('stock_market.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_holiday = db.Column(db.Boolean, default=False)
    note = db.Column(db.String(255))

    def __repr__(self):
        status = "Holiday" if self.is_holiday else "Open"
        return f"<MarketSchedule {self.market.name} {self.start_date} to {self.end_date} ({status})>"

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
            session['user_id'] = user.id
            return redirect(url_for('customer_home'))
        elif admin:
            session['admin_id'] = admin.id
            return redirect(url_for('admin_home'))
        else:
            flash('Invalid email or password', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/customer_home', methods=['GET', 'POST'])
def customer_home():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))

    user = User.query.get(user_id)

    if request.method == 'POST':
        stock_id = request.form.get('stock_id')
        quantity = Decimal(request.form.get('quantity', 0))
        action = request.form.get('action')  # "buy" or "sell"

        stock = StockMarket.query.get(stock_id)
        if not stock:
            flash("Stock not found.", "danger")
            return redirect(url_for('customer_home'))

        if action == "buy":
            total_cost = stock.price * quantity

            # Update portfolio
            portfolio_entry = Portfolio.query.filter_by(user_id=user.id, stock_id=stock.id).first()
            if portfolio_entry:
                old_total_value = portfolio_entry.avg_purchase_price * portfolio_entry.quantity
                new_total_value = old_total_value + total_cost
                portfolio_entry.quantity += quantity
                portfolio_entry.avg_purchase_price = new_total_value / portfolio_entry.quantity
            else:
                portfolio_entry = Portfolio(
                    user_id=user.id,
                    stock_id=stock.id,
                    quantity=quantity,
                    avg_purchase_price=stock.price
                )
                db.session.add(portfolio_entry)

            # Record order and transaction
            order = OrderHistory(
                user_id=user.id,
                stock_id=stock.id,
                order_type="BUY",
                quantity=quantity,
                price=stock.price,
                total_cost=total_cost,
                order_placed_at=datetime.utcnow(),
                executed=True
            )
            db.session.add(order)

            transaction = FinancialTransaction(
                user_id=user.id,
                amount=total_cost,
                transaction_type="WITHDRAWAL",
                related_order=order
            )
            db.session.add(transaction)
            db.session.commit()

            flash(f"Successfully bought {quantity} of {stock.ticker_symbol}", "success")
            return redirect(url_for('customer_home'))

        elif action == "sell":
            portfolio_entry = Portfolio.query.filter_by(user_id=user.id, stock_id=stock.id).first()
            if not portfolio_entry or portfolio_entry.quantity < quantity:
                flash("Not enough stock to sell", "danger")
                return redirect(url_for('customer_home'))

            total_sale = stock.price * quantity
            portfolio_entry.quantity -= quantity
            if portfolio_entry.quantity <= 0:
                db.session.delete(portfolio_entry)

            # Record order and transaction
            order = OrderHistory(
                user_id=user.id,
                stock_id=stock.id,
                order_type="SELL",
                quantity=quantity,
                price=stock.price,
                total_cost=total_sale,
                order_placed_at=datetime.utcnow(),
                executed=True
            )
            db.session.add(order)

            transaction = FinancialTransaction(
                user_id=user.id,
                amount=total_sale,
                transaction_type="DEPOSIT",
                related_order=order
            )
            db.session.add(transaction)
            db.session.commit()

            flash(f"Successfully sold {quantity} of {stock.ticker_symbol}", "success")
            return redirect(url_for('customer_home'))

    stocks = StockMarket.query.all()

    return render_template(
        'customer_home.html',
        user=user,
        stocks=stocks
    )

@app.route('/admin_home', methods=['GET', 'POST'])
def admin_home():
    admin_id = session.get('admin_id')
    if not admin_id:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        company_name = request.form.get('company_name')
        ticker = request.form.get('ticker')
        price = request.form.get('price')
        industry = request.form.get('industry')
        country = request.form.get('country')

        new_stock = StockMarket(
            company_name=company_name,
            ticker_symbol=ticker,
            price=price,
            industry=industry,
            country=country,
        )

        db.session.add(new_stock)
        db.session.commit()

        flash(f"Stock {ticker} created successfully!", "success")
        return redirect(url_for('admin_home'))

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

@app.route('/deposit')
def deposit():
    return render_template('deposit.html')

@app.route('/withdraw')
def withdraw():
    return render_template('withdraw.html')

@app.route('/transactions')
def transactions():
    return render_template('transactions.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))

    user = User.query.get(user_id)

    if request.method == 'POST':
        # Get the form data
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')

        # Check if email is being changed and if it's already in use
        if email != user.email and User.query.filter_by(email=email).first():
            flash("Email already in use!", "danger")
            return redirect(url_for('settings'))

        # Update user information
        user.first_name = first_name
        user.last_name = last_name
        user.email = email

        try:
            db.session.commit()
            flash("Settings updated successfully!", "success")
        except:
            db.session.rollback()
            flash("An error occurred while updating settings.", "danger")

        return redirect(url_for('settings'))

    return render_template('settings.html', user=user)

if __name__ == '__main__':
    app.run(debug=True)