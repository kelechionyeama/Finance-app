import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Get stocks from user for display
    stocks = db.execute("SELECT symbol, stock, price, SUM(shares) AS tshares FROM transactions WHERE user_id = (?) GROUP BY symbol", session["user_id"])

    # Get user cash
    cash = db.execute("SELECT cash FROM users WHERE id = (?)", session["user_id"])[0]["cash"]

    # Get user cash plus stock value
    total = cash

    # Add together
    for stock in stocks:
        price = lookup(stock["symbol"])["price"]
        totals = price * stock["tshares"]
        stock.update({'price': price, 'total': total})
        total += totals

    return render_template("index.html", stocks=stocks, cash=cash, total=total, usd=usd)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # Some variables
    Buy = "Buy"

    if request.method == "POST":

        # Check Parameters
        if not request.form.get("symbol"):
            return apology("Symbol cannot be blank", 400)

        # Check share is numeric data type
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("INVALID SHARES")
        # Check shares is positive number
        if not (shares >= 0):
            return apology("INVALID SHARES")

        elif not lookup(request.form.get("symbol")):
            return apology("Symbol does not exsist", 400)

        # Get cash of user. Cash is a dict in list i.e [{}]
        CASH = db.execute("SELECT cash FROM users WHERE id IN (?)", session["user_id"])[0]["cash"]

        # Get price and symbol. both are dicts
        Stock = lookup(request.form.get("symbol"))["name"]
        Price = lookup(request.form.get("symbol"))["price"]

        # Check if the user has enough money
        if Price*float(request.form.get("shares")) > CASH:
            return apology("Insufficient funds", 400)

        # New cash balance after buying shares
        NewCash = CASH - (Price * float(request.form.get("shares")))

        # Store information in the database
        db.execute("INSERT INTO transactions (ordertype, stock, shares, price, user_id, symbol) VALUES(?,?,?,?,?,?)",
                   Buy, Stock, request.form.get("shares"), Price, session["user_id"], request.form.get("symbol").upper())

        # Update cash balance
        db.execute("UPDATE users SET cash = (?) WHERE id = (?)", NewCash, session["user_id"])

        return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT ordertype, symbol, shares, price, time FROM transactions WHERE user_id = (?)", session["user_id"])

    return render_template("history.html", history=history)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        # Check parameters
        if not request.form.get("symbol"):
            return apology("Please enter a symbol", 400)

        if not lookup(request.form.get("symbol")):
            return apology("Invalid symbol", 400)

        # Get name,symbol and price from API using "lookup"
        DATA = lookup(request.form.get("symbol"))
        return render_template("quoted.html", DATA=DATA, usd=usd)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # When form is submitted
    if request.method == "POST":

        # Ensure all these parameters
        if not request.form.get("username"):
            return apology("must provide a username", 400)

        elif not request.form.get("password"):
            return apology("must provide a password", 400)

        elif not request.form.get("confirmation"):
            return apology("must provide a password", 400)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords do not match!", 400)

        # Store username & password into database if username has not been taken
        try:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)",
            request.form.get("username"), generate_password_hash(request.form.get("password"), "pbkdf2:sha256", len(request.form.get("password"))))

        except:
            return apology("Username has been taken", 400)

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Some Variables
    Sell = "Sell"

    # User stocks selected as symbols
    stocks = db.execute("SELECT symbol, SUM(shares) AS tshares FROM transactions WHERE user_id = (?) GROUP BY symbol", session["user_id"])

    if request.method == "POST":

        # Check these paramters
        if not request.form.get("symbol"):
            return apology("No stock selected", 400)

        if not request.form.get("shares"):
            return apology("No quantity selected", 400)

        if float(request.form.get("shares")) <= 0:
            return apology("Quantity less than 1", 400)

        # Check if user has enough shares to sell
        amount_of_shares = db.execute("SELECT SUM(shares) AS value FROM transactions WHERE user_id = (?) AND symbol = (?) GROUP BY symbol",
                                       session["user_id"], request.form.get("symbol"))[0]["value"]

        if float(request.form.get("shares")) > float(amount_of_shares):
            return apology("Not enough shares", 400)

        #Get price of stock user wants to sell
        Price = lookup(request.form.get("symbol"))["price"]

        # Get stock user wants to sell
        Stock = lookup(request.form.get("symbol"))["name"]

        # Calculate price of sale
        Sale = Price * float(request.form.get("shares"))

        # Add sale money to cash balance
        db.execute("UPDATE users SET cash = (cash + (?)) WHERE id = (?)", Sale, session["user_id"])

        NewShares = -float((request.form.get("shares")))

        # Update database with information
        db.execute("INSERT INTO transactions (ordertype, stock, shares, price, user_id, symbol) VALUES(?,?,?,?,?,?)",
                   Sell, Stock, NewShares, Price, session["user_id"], request.form.get("symbol").upper())

        return redirect("/")

    return render_template("sell.html", stocks=stocks)

