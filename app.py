from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from decimal import Decimal
from datetime import datetime, timedelta
import random
from werkzeug.security import generate_password_hash, check_password_hash
import holidays

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://admin:Triostuds69!@vpn-db.cboyqwso4bjq.us-east-2.rds.amazonaws.com/vpn_db'
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
    ticker_symbol = db.Column(db.String(5), unique=True, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    company_name = db.Column(db.String(150), nullable=False)
    volume = db.Column(db.Numeric(5), nullable=False)
    trend = db.Column(db.String(10), nullable=True)
    shares_outstanding = db.Column(db.BigInteger, nullable=False, default=volume)
    daily_high = db.Column(db.Numeric(10, 2), nullable=False, default=price)
    daily_low = db.Column(db.Numeric(10, 2), nullable=False, default=price)

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
    order_placed_at = db.Column(db.DateTime, default=datetime.now())
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
    timestamp = db.Column(db.DateTime, default=datetime.now())

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
    opening_time = db.Column(db.Time, nullable=False, default=datetime.strptime('9:00 AM', '%I:%M %p').time())
    closing_time = db.Column(db.Time, nullable=False, default=datetime.strptime('5:00 PM', '%I:%M %p').time())
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<MarketHours {self.opening_time}-{self.closing_time} {'Active' if self.is_active else 'Inactive'}>"

class MarketSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_day = db.Column(db.String(10), nullable=False, default="Monday")
    end_day = db.Column(db.String(10), nullable=False, default="Friday")
    is_holiday = db.Column(db.Boolean, default=False)
    note = db.Column(db.String(255))

    def __repr__(self):
        status = "Holiday" if self.is_holiday else "Open"
        return f"<MarketSchedule {self.market.name} {self.start_date} to {self.end_date} ({status})>"
    
class MarketHoliday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)

with app.app_context():
    db.create_all()

    if not MarketHours.query.first():
        default_hours = MarketHours()
        db.session.add(default_hours)
        db.session.commit()

    if not MarketSchedule.query.first():
        db.session.add(MarketSchedule(start_day="Monday", end_day="Friday", note="Monday - Friday"))
        db.session.commit()

def assign_trends():
    with app.app_context():
        stocks = StockMarket.query.all()
        for stock in stocks:
            stock.trend = random.choice(["bullish", "bearish"])
            print(f"{stock.ticker_symbol} is {stock.trend} now.")
        db.session.commit()

# Random Price Generator
def update_stock_price():
    with app.app_context():
        if not is_market_open():
            print("Market is closed. Skipping price update.")
            return

        stocks = StockMarket.query.all()
        for stock in stocks:
            if stock.trend == "bullish":
                change = random.uniform(-0.005, 0.015)
            elif stock.trend == "bearish":
                change = random.uniform(-0.015, 0.005)
            else:
                change = random.uniform(-0.01, 0.01)

            new_price = float(stock.price) * (1 + change)
            stock.price = max(new_price, 0)

            if new_price >= stock.daily_high:
                stock.daily_high = new_price
            if new_price <= stock.daily_low:
                stock.daily_low = new_price
            
            print(f"{stock.ticker_symbol} ({stock.trend}): ${stock.price:.2f} ({change*100:+.2f}%)")

        db.session.commit()

def reset_daily_high_and_low():
    with app.app_context():
        stocks = StockMarket.query.all()
        for stock in stocks:
            stock.daily_high = stock.price
            stock.daily_low = stock.price
        db.session.commit()

def is_market_open():
    market_schedule = MarketSchedule.query.first()
    market_hours = MarketHours.query.first()
    current_time = datetime.now().time()
    today = datetime.now().strftime("%A")
    holiday_check = datetime.now().date()

    us_holidays = holidays.UnitedStates()
    if holiday_check in us_holidays:
        return False
    
    market_holiday = MarketHoliday.query.filter_by(date=holiday_check).first()
    if market_holiday:
        return False

    if not market_schedule or market_schedule.is_holiday:
        return False

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    start_index = days.index(market_schedule.start_day)
    end_index = days.index(market_schedule.end_day)
    today_index = days.index(today)

    if start_index <= end_index:
        in_day_range = start_index <= today_index <= end_index
    else:
        in_day_range = today_index >= start_index or today_index <= end_index

    # handles overnight sessions (example: 7 PM - 3 AM)
    if market_hours and market_hours.is_active:
        open_t = market_hours.opening_time
        close_t = market_hours.closing_time

        if open_t < close_t:
            in_time_range = open_t <= current_time <= close_t
        else:
            # Overnight case (spans midnight)
            in_time_range = current_time >= open_t or current_time <= close_t
    else:
        in_time_range = False

    return in_day_range and in_time_range

def update_high_and_low():
    with app.app_context():
        stocks = StockMarket.query.all()

        for stock in stocks:
            price = stock.price
            if price > stock.daily_high:
                stock.daily_high = price
            if price < stock.daily_low:
                stock.daily_low = price

        db.session.commit()

@app.before_request
def check_admin_exists():
    # Allow access to setup route if admin doesn't exist yet
    allowed_routes = ['setup_admin']
    
    if Administrator.query.count() == 0 and request.endpoint not in allowed_routes:
        return redirect(url_for('setup_admin'))

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
            volume = stock.volume
            
            if total_cost > user.cash:
                flash("Insufficient funds.", "danger")
                return redirect(url_for('customer_home'))
            
            if quantity > volume:
                flash("Insufficient stock volume.", "danger")
                return redirect(url_for('customer_home'))
            
            else:
                if is_market_open():
                    # Update portfolio
                    portfolio_entry = Portfolio.query.filter_by(user_id=user.id, stock_id=stock.id).first()
                    stock.volume -= quantity

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
                        order_placed_at=datetime.now(),
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
                
                else:
                    flash("Market is closed.", "danger")
                    return redirect(url_for('customer_home'))

        elif action == "sell":
            if is_market_open():
                portfolio_entry = Portfolio.query.filter_by(user_id=user.id, stock_id=stock.id).first()
                if not portfolio_entry or portfolio_entry.quantity < quantity:
                    flash("Not enough stock to sell", "danger")
                    return redirect(url_for('customer_home'))

                total_sale = stock.price * quantity
                portfolio_entry.quantity -= quantity
                stock.volume += quantity

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
                    order_placed_at=datetime.now(),
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
            
            else:
                flash("Market is closed.", "danger")
                return redirect(url_for('customer_home'))

    stocks = StockMarket.query.all()

    # Pagination logic for stocks
    page = request.args.get('page', 1, type=int)  # Get the current page number from the query string
    per_page = 7  # Number of stocks per page
    stocks_pagination = StockMarket.query.paginate(page=page, per_page=per_page, error_out=False)
    paginated_stocks = stocks_pagination.items  # Get the stocks for the current page

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

    market_schedule = MarketSchedule.query.first()
    market_hours = MarketHours.query.first()
    market_open = is_market_open()

    return render_template(
        'customer_home.html',
        user=user,
        stocks=stocks,
        stocks_pagination=stocks_pagination,
        portfolio=portfolio,
        portfolio_data=portfolio_data,
        market_hours=market_hours,
        market_open=market_open,
        market_schedule=market_schedule,
        paginated_stocks=paginated_stocks
    )

@app.route('/admin_home', methods=['GET', 'POST'])
def admin_home():
    admin_id = session.get('admin_id')
    if not admin_id:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))
    
    market_hours = MarketHours.query.first()
    market_schedule = MarketSchedule.query.first() #added for market schedule

    if request.method == 'POST':
        if 'add_holiday' in request.form:
            holiday_date = request.form.get('holiday_date')
            holiday_name = request.form.get('holiday_name')

            if not holiday_date or not holiday_name:
                flash("Please enter both a date and name for the holiday.", "warning")
                return redirect(url_for('admin_home'))

            existing = MarketHoliday.query.filter_by(date=holiday_date).first()
            us_holidays = holidays.UnitedStates()
            if existing or holiday_date in us_holidays:
                flash("A holiday already exists on that date.", "warning")
                return redirect(url_for('admin_home'))

            try:
                new_holiday = MarketHoliday(date=holiday_date, name=holiday_name)
                db.session.add(new_holiday)
                db.session.commit()
                flash(f"Added holiday: {holiday_name} ({holiday_date})", "success")
            except Exception as e:
                db.session.rollback()
                flash("Error adding holiday. Please check your input.", "danger")

            return redirect(url_for('admin_home'))
        
        company_name = request.form.get('company_name')
        ticker = request.form.get('ticker')
        price = request.form.get('price')
        volume = request.form.get('volume')

        try:
            new_stock = StockMarket(
            company_name=company_name,
            ticker_symbol=ticker,
            price=price,
            volume=volume,
        )
            db.session.add(new_stock)
            db.session.commit()
            flash(f"Stock {ticker} created successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred: Make sure stock is unique and input values are valid.", "danger")

        return redirect(url_for('admin_home'))

    return render_template('admin_home.html', market_hours=market_hours, market_schedule=market_schedule) #added market_schedule

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
        existing_admin = Administrator.query.filter_by(email=email).first()

        if existing_user or existing_admin:
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

@app.route('/setup_admin', methods=['GET', 'POST'])
def setup_admin():
    # If admin already exists, prevent setup
    if Administrator.query.count() > 0:
        flash("Admin account already exists!", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        session.clear()

        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        existing_admin = Administrator.query.filter_by(email=email).first()
        existing_user = User.query.filter_by(email=email).first()

        if existing_admin or existing_user:
            flash("Email is already registered!", "danger")
            return redirect(url_for('setup_admin'))
        
        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('setup_admin'))

        hashed_password = generate_password_hash(password)

        new_admin = Administrator(
            email=email,
            password=hashed_password
        )

        db.session.add(new_admin)
        db.session.commit()

        flash("Admin account created successfully!", "success")
        return redirect(url_for('login'))

    return render_template('setup_admin.html')

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

    page = request.args.get('page', 1, type=int)
    per_page = 10

    pagination = FinancialTransaction.query.filter_by(user_id=user.id) \
        .order_by(FinancialTransaction.timestamp.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)

    transactions = pagination.items

    return render_template('transactions.html', user=user, transactions=transactions, pagination=pagination)

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
            new_password = request.form.get('password')
            confirm_new_password = request.form.get('confirm_new_password')

            # Check if email is being changed and if it's already in use
            if email != user.email and User.query.filter_by(email=email).first():
                flash("Email already in use!", "danger")
                return redirect(url_for('settings'))

            # Update user information
            user.first_name = first_name
            user.last_name = last_name
            user.email = email

            if new_password:
                if new_password != confirm_new_password:
                    flash("Passwords do not match!", "danger")
                    return redirect(url_for('settings'))
                user.password = generate_password_hash(new_password)

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
        new_password = request.form.get('password')
        confirm_new_password = request.form.get('confirm_new_password')

        # Check if email is being changed and already in use
        if email != admin.email and Administrator.query.filter_by(email=email).first():
            flash("Email already in use!", "danger")
            return redirect(url_for('admin_settings'))

        # Update admin email
        admin.email = email

        if new_password:
            if new_password != confirm_new_password:
                flash("Passwords do not match!", "danger")
                return redirect(url_for('settings'))
            admin.password = generate_password_hash(new_password)

        try:
            db.session.commit()
            flash("Admin information updated successfully!", "success")
        except:
            db.session.rollback()
            flash("An error occurred while updating admin email.", "danger")

    return render_template("admin_settings.html", admin=admin)

@app.route('/update_market_hours', methods=['POST'])
def update_market_hours():
    if not session.get('admin_id'):
        flash("Unauthorized access", "danger")
        return redirect(url_for('login'))

    try:
        opening_hour = request.form.get('opening_hour')
        opening_meridiem = request.form.get('opening_meridiem')
        closing_hour = request.form.get('closing_hour')
        closing_meridiem = request.form.get('closing_meridiem')

        # Convert to 24-hour format
        opening_time = datetime.strptime(f"{opening_hour}:00 {opening_meridiem}", "%I:%M %p").time()
        closing_time = datetime.strptime(f"{closing_hour}:00 {closing_meridiem}", "%I:%M %p").time()

        # Update or create market hours
        market_hours = MarketHours.query.first()
        if not market_hours:
            market_hours = MarketHours()

        market_hours.opening_time = opening_time
        market_hours.closing_time = closing_time
        
        db.session.add(market_hours)
        db.session.commit()

        flash("Market hours updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating market hours: {str(e)}", "danger")

    return redirect(url_for('admin_home'))

@app.route('/update_market_schedule', methods=['POST'])
def update_market_schedule():
    if not session.get('admin_id'):
        flash("Unauthorized access", "danger")
        return redirect(url_for('login'))

    # Retreive the start and end days from the form
    try:
        start_day = request.form.get('start_date')
        end_day = request.form.get('end_date')

        # Fetching the existing market schedule configuration
        market_schedule = MarketSchedule.query.first()
        if not market_schedule:
            market_schedule = MarketSchedule()

        # Updating the market schedule with new values
        market_schedule.start_day = start_day
        market_schedule.end_day = end_day
        market_schedule.note = f"{start_day} - {end_day}"

        # Saving the changes to the database
        db.session.add(market_schedule)
        db.session.commit()

        flash("Market schedule updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating market schedule: {str(e)}", "danger")

    return redirect(url_for('admin_home'))

@app.route('/logout')
def logout():
    session.clear()  # This clears all session data
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

scheduler.start()
scheduler.add_job(id="Assign Trends", func=assign_trends, trigger="interval", minutes=30)
scheduler.add_job(id="Update Stock Price", func=update_stock_price, trigger="interval", seconds=30)
scheduler.add_job(id="Reset daily high and low values", func=reset_daily_high_and_low, trigger="cron", day_of_week="mon-sun", hour=0, minute=0)

if __name__ == '__main__':
    app.run(debug=True)