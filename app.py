from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/customer_home')
def customer_home():
    return render_template('customer_home.html')

if __name__ == '__main__':
    app.run(debug=True)