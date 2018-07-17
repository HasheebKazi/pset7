import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Ensure environment variable is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    row = db.execute("SELECT symbol, SUM(shares) AS :totalshares FROM transactions WHERE userID=:userid GROUP BY symbol", totalshares="totalShares",userid=session["user_id"])
    if len(row) < 1:
        return apology("buy something!", 403)

    cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    cash = round(float(cash[0]["cash"]), 2)

    portfolio = list(); total = 0;

    for stock in row:
        quote = lookup(stock["symbol"])
        price = round(float(quote["price"]), 2)
        total_shares = int(stock["totalShares"])

        if total_shares <= 0:
            continue

        cost = round(total_shares*price, 2)
        total += cost


        portfolio.append({
            "symbol": quote["symbol"].upper(),
            "totalShares": stock["totalShares"],
            "currentPrice": price,
            "totalValue":  cost
        })

    return render_template("index.html", portfolio=portfolio, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        symbol2 = request.form.get("symbol").upper()
        shares = int(request.form.get("shares"))

        quote = lookup(symbol2)

        if quote == None:
            return apology("Invalid symbol", 403)
        if shares < 1:
            return apology("Invalid number of shares", 403)

        row = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
        cash = round(float(row[0]["cash"]), 2)
        price2 = round(float(quote["price"]), 2)
        cost = round(shares*price2, 2)
        remaining_cash = round(cash - cost, 2)
        if cost > cash:
            return apology("Not enough money :(", 403)
        else:
            # update users cash
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", id=session["user_id"], cash=remaining_cash)
            # update transactions table
            db.execute("INSERT INTO transactions (userID, symbol, price, shares, cost) VALUES (:userID, :symbol, :price, :shares, :cost)", userID=session["user_id"], symbol=symbol2, price=price2, shares=shares, cost=cost)

        return render_template("buy.html")
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    row = db.execute("SELECT * FROM transactions WHERE userID=:userid", userid=session["user_id"])

    cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    cash = round(float(cash[0]["cash"]), 2)

    transactions = list();

    for stock in row:
        transactions.append({
            "symbol": stock["symbol"],
            "price": stock["price"],
            "shares": stock["shares"],
            "cost":  stock["cost"]
        })

    return render_template("history.html", transactions=transactions, cash=cash)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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

        stockSymbol = request.form.get("symbol").upper();

        info = lookup(stockSymbol)

        if info == None:
            return apology("Invalid stock ticker", 403)
        else:
            return render_template("quoted.html", symbol=info)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # intercept post request made by user creating a new account
    if request.method == "POST":
        username1 = request.form.get("username")
        # check for unique and valid Username
        username_table = db.execute("SELECT * FROM users WHERE username = :username", username=username1)
        if len(username_table)>0:
                return apology("Username is taken, please select a new one", 403)
        print(1)
        # check for valid Password (password and password confirmation match)
        password2 = request.form.get("confirmation")
        if request.form.get("password") != password2:
                return apology("Passwords do not match, please try again", 403)
        print(2)
        # if username is valid and passwords match
        password_hash = generate_password_hash(password2)

        db.execute("INSERT INTO users (username, hash) VALUES (:username, :password)", username=username1, password=password_hash)

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        row = db.execute("SELECT symbol, SUM(shares) AS :totalshares FROM transactions WHERE userID=:userid GROUP BY symbol", totalshares="totalShares",userid=session["user_id"])
        symbolList = []
        for x in row:
            symbolList.append(x["symbol"])

        ticker = request.form.get("symbol");
        sharesSell = int(request.form.get("shares"))

        if not ticker in symbolList:
            return apology("No such stock in portfolio", 403)

        portfolio = list();

        for stock in row:
            quote = lookup(stock["symbol"])
            price = round(float(quote["price"]), 2)
            total_shares = int(stock["totalShares"])

            portfolio.append({
                "symbol": quote["symbol"].upper(),
                "totalShares": stock["totalShares"],
                "currentPrice": price,
            })

        def search(name):
            for p in portfolio:
                if p['symbol'] == name:
                    return p

        correctRow = search(ticker)

        if correctRow["totalShares"] < sharesSell:
            return apology("Not enough shares", 403)
        else:
            money = round(sharesSell*correctRow["currentPrice"], 2)
            cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
            cash = round(float(cash[0]["cash"]), 2)
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", id=session["user_id"], cash=cash+money)
            db.execute("INSERT INTO transactions (userID, symbol, price, shares, cost) VALUES (:userID, :symbol, :price, :shares, :cost)", userID=session["user_id"], symbol=ticker, price=correctRow["currentPrice"], shares=-sharesSell, cost=0)

        return redirect("/")

    else:
        row = db.execute("SELECT symbol, SUM(shares) AS :totalshares FROM transactions WHERE userID=:userid GROUP BY symbol", totalshares="totalShares",userid=session["user_id"])

        symbolList = []
        for x in row:
            if x["totalShares"] <= 0:
                continue
            symbolList.append(x["symbol"])

        return render_template("sell.html", symbol=symbolList)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
