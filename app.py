from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

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

    def __repr__(self):
        return f"<User {self.email}>"
    
banks = db.relationship('BankInfo', backref='user', lazy=True)

class BankInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    institute_name = db.Column(db.String(100))
    routing_number = db.Column(db.String(20))
    account_number = db.Column(db.String(20))

    def __repr__(self):
        return f"<User {User.email}"
    
with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email, password=password).first()

        if user:
            return redirect(url_for('customer_home'))
        else:
            flash('Invalid email or password', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/customer_home')
def customer_home():
    return render_template('customer_home.html')

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