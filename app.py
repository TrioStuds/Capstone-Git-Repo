from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from decimal import Decimal
from datetime import datetime, timedelta
import random
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:password@localhost/vpn_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'vpn_secret_key'

db = SQLAlchemy(app)

scheduler = APScheduler()
scheduler.init_app(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(1024), nullable=False)
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
    funds = db.Column(db.Numeric(12, 2), nullable=False, default=10000)

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
    password = db.Column(db.String(1024), nullable=False)

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
            password=generate_password_hash("password")
        )
        db.session.add(admin_user)
        db.session.commit()

# Random Price Generator
def update_stock_price():
    with app.app_context():
        stocks = StockMarket.query.all()
        for stock in stocks:
            new_price = float(stock.price) * (1 + random.uniform(-0.01, 0.01))
            stock.price = max(new_price, 0)
            print(f"Stock: {stock.ticker_symbol} updated to ${stock.price:.2f}")
        db.session.commit()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        admin = Administrator.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('customer_home'))
        elif admin and check_password_hash(admin.password, password):
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
    portfolio = Portfolio.query.filter_by(user_id=user.id).all()

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
            
            if total_cost > user.cash:
                flash("Insufficient funds.", "danger")
                return redirect(url_for('customer_home'))
            
            else:
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
                user.cash -= total_cost
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
            user.cash += total_sale
            db.session.commit()

            flash(f"Successfully sold {quantity} of {stock.ticker_symbol}", "success")
            return redirect(url_for('customer_home'))

    stocks = StockMarket.query.all()

    portfolio_data = []
    for entry in portfolio:
        try:
            if float(entry.quantity) > 0:  # Only include stocks that user owns
                current_value = float(entry.quantity * entry.stock.price)
                portfolio_data.append({
                    'symbol': entry.stock.ticker_symbol,
                    'value': current_value
                })
        except (TypeError, ValueError) as e:
            print(f"Error processing portfolio entry: {e}")
            continue

    return render_template(
        'customer_home.html',
        user=user,
        stocks=stocks,
        portfolio=portfolio,
        portfolio_data=portfolio_data
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

        session.clear()

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
        
        hashed_password = generate_password_hash(password)

        new_user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=hashed_password
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

            session['user_id'] = new_user.id

            db.session.add(new_bank)
            db.session.commit()

        flash("Account created successfully!", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    bank_accounts = BankInfo.query.filter_by(user_id=user.id).all()

    if request.method == 'POST':
        try:
            amount = Decimal(request.form.get('amount', 0))
            bank_id = request.form.get('bank_id')

            bank_account = BankInfo.query.filter_by(id=bank_id, user_id=user.id).first()
            if not bank_account:
                flash("Invalid bank account selected.", "danger")
                return redirect(url_for('deposit'))

            if amount <= 0:
                flash("Deposit amount must be positive.", "danger")
                return redirect(url_for('deposit'))

            if amount > bank_account.funds:
                flash("Insufficient funds in bank account.", "danger")
                return redirect(url_for('deposit'))

            bank_account.funds -= amount
            user.cash += amount

            transaction = FinancialTransaction(
                user_id=user.id,
                amount=amount,
                transaction_type="DEPOSIT",
                related_order=None
            )

            db.session.add(transaction)
            db.session.commit()

            flash(f"Successfully deposited ${amount} from {bank_account.institute_name}", "success")
            return redirect(url_for('customer_home'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error processing deposit: {str(e)}", "danger")
            return redirect(url_for('deposit'))

    # Render form with only this user's banks
    return render_template("deposit.html", user=user, bank_accounts=bank_accounts)

@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))
    
    user = User.query.get(user_id)
    bank_accounts = BankInfo.query.filter_by(user_id=user.id).all()

    if request.method == 'POST':
        try:
            amount = Decimal(request.form.get('amount', 0))
            bank_id = request.form.get('bank_id')

            bank_account = BankInfo.query.filter_by(id=bank_id, user_id=user.id).first()
            if not bank_account:
                flash("Invalid bank account selected.", "danger")
                return redirect(url_for('withdraw'))
            
            if amount <= 0:
                flash("Withdrawal amount must be positive.", "danger")
                return redirect(url_for('withdraw'))
            
            if amount > user.cash:
                flash("Insufficient funds in account.", "danger")
                return redirect(url_for('withdraw'))

            bank_account.funds += amount
            user.cash -= amount

            transaction = FinancialTransaction(
                user_id=user.id,
                amount=amount,
                transaction_type="WITHDRAWAL",
                related_order=None
            )

            db.session.add(transaction)
            db.session.commit()

            flash(f"Successfully withdrew ${amount} from your portfolio to your bank account, {bank_account.institute_name}", "success")
            return redirect(url_for('customer_home'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error processing withdrawal: {str(e)}", "danger")
            return redirect(url_for('withdraw'))
        
    return render_template('withdraw.html', user=user, bank_accounts=bank_accounts)

@app.route('/transactions')
def transactions():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))
    
    user = User.query.get(user_id)
    transactions = FinancialTransaction.query.filter_by(user_id=user.id).order_by(FinancialTransaction.timestamp.desc()).all()
    return render_template('transactions.html', user=user, transactions=transactions)
    #return render_template('transactions.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))

    user = User.query.get(user_id)

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'personal':
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

        elif form_type == 'bank':
            # Get bank form info
            institute_name = request.form.get('institute_name')
            routing_number = request.form.get('routing_number')
            account_number = request.form.get('account_number')

            if not (institute_name and routing_number and account_number):
                flash("Please fill out all bank fields.", "danger")
                return redirect(url_for('settings'))

            # check if bank account already exists
            existing_bank = BankInfo.query.filter_by(
                user_id=user.id,
                institute_name=institute_name,
                routing_number=routing_number,
                account_number=account_number
            ).first()

            if existing_bank:
                flash("This bank account is already added.", "warning")
                return redirect(url_for('settings'))

            new_bank = BankInfo(
                user_id=user.id,
                institute_name=institute_name,
                routing_number=routing_number,
                account_number=account_number
            )
            db.session.add(new_bank)

            try:
                db.session.commit()
                flash("Bank account added successfully!", "success")
            except:
                db.session.rollback()
                flash("An error occurred while adding the bank account.", "danger")

        return redirect(url_for('settings'))

    return render_template('settings.html', user=user)

@app.route('/admin_settings', methods=['GET', 'POST'])
def admin_settings():
    admin_id = session.get('admin_id')
    if not admin_id:
        flash("Please log in as admin first", "warning")
        return redirect(url_for('admin_login'))

    admin = Administrator.query.get(admin_id)

    if request.method == 'POST':
        # Get form data
        email = request.form.get('email')

        # Check if email is being changed and already in use
        if email != admin.email and Administrator.query.filter_by(email=email).first():
            flash("Email already in use!", "danger")
            return redirect(url_for('admin_settings'))

        # Update admin email
        admin.email = email

        try:
            db.session.commit()
            flash("Admin email updated successfully!", "success")
        except:
            db.session.rollback()
            flash("An error occurred while updating admin email.", "danger")

    return render_template("admin_settings.html", admin=admin)

@app.route('/logout')
def logout():
    session.clear()  # This clears all session data
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

scheduler.start()
scheduler.add_job(id="Update Stock Price", func=update_stock_price, trigger="interval", seconds=30)

if __name__ == '__main__':
    app.run(debug=True)