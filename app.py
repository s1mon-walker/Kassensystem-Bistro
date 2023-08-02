from datetime import datetime, timedelta
import os
import time
import json
import logging
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session
import sql_db
from weather_api import get_local_weather

# configure folder for file downloads
app = Flask(__name__)
app.secret_key = ''
app.permanent_session_lifetime = timedelta(days=1)
app.config['UPLOAD_FOLDER'] = 'uploads'

# setup logging
c_handler = logging.StreamHandler()
f_handler = logging.FileHandler('app.log')
formater = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
c_handler.setFormatter(formater)
f_handler.setFormatter(formater)
app.logger.setLevel(logging.DEBUG)
# app.logger.addHandler(c_handler)
app.logger.addHandler(f_handler)
app.logger.info('Application started')

# ToDo:
# - Server läuft auf RPI
# - Integritätsprüfung der Bestellungen: order_id noch verbessern (wieso so inkonsistent, cache?)
# - Anzeigen Anteil am Tagesumsatz pro Produkt
# - Änderungen am Produkt erzeugen im Hintergrund ein neues Produkt (ID)
# - Saubere Integration von Spetzialprodukten (Kostenstelle)
# - (Drag and Drop Buttons in Kasse)
# - Wetter des Tages speichern können
# - Neue Tabelle daydata DATE, base_cash, weather
# - Lagerhaltung, Rohstoffkosten, Personalstunden, nachkorrigieren der Zahlen
# - Bestellnummer tracking und abarbeitungssystem
# - Screen zu darstellen der fertigen bestellungen, ausbuchen der abgeholten Bestellungen

# Paymentmethods
CASH = 0
CARD = 1
TWINT = 2 
STAFF = 3

# Special sales positions
TOYS = 0
TREATS = 1

base_cash = sql_db.get_base_cash()
revenue = [0.0, 0.0, 0.0, 0.0] # [CASH, CARD, TWINT, STAFF]
sales = [0.0, 0.0]
cash_now = 0
date = datetime.today().strftime('%Y-%m-%d')

order_id = sql_db.get_new_order_id()

def register_order(order:list, id, payment_method:int):
    sql_db.insert_order(id, payment_method, order)
    calc_cash()

def calc_cash(date=None):
    global base_cash
    global revenue
    global sales
    global cash_now

    revenue, sales = sql_db.calc_todays_revenue(date)
    cash_now = base_cash + revenue[CASH]

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/kasse', methods=['POST', 'GET'])
def kasse():
    global order_id

    if request.method == 'POST':
        data = request.data.decode()
        app.logger.debug('Data recived: %s', data)
        json_object = json.loads(data)
        id = json_object['order_id']
        order = json_object['order']
        payment_method = json_object['payment_method']
        new_id = sql_db.get_new_order_id()
        if id != new_id:
            app.logger.warning(f'Order ID mismatch got:{id} expected:{new_id}')
        register_order(order, id, payment_method)
        app.logger.info(f'Order {id} registerd')
        order_id += 1
        app.logger.debug(f'Order ID incremented to {order_id}')
    
    products = sql_db.get_all_products_dict()
    colors = sql_db.get_colors_dict()
    
    return render_template('kasse.html', products=products, order_id=order_id, colors=colors)

@app.route('/kueche')
def kueche():
    orders = sql_db.get_todays_orders(n=5) # [id, datetime, payment_method, products]
    orders = list(map(lambda o:format_order(o), orders))
    return render_template('kueche.html', orders=orders)

@app.route('/bestellungen')
def bestellungen():
    orders = sql_db.get_todays_orders() # [id, datetime, payment_method, products]
    orders = list(map(lambda o:format_order(o), orders))
    return render_template('bestellungen.html', orders=orders)

def format_order(order):
    order = list(order)
    if order[2] == CASH:
        order[2] = 'Bar'
    elif order[2] == CARD:
        order[2] = 'Karte'
    elif order[2] == TWINT:
        order[2] = 'TWINT'
    elif order[2] == STAFF:
        order[2] = 'Helfer'
    else:
        order[2] = 'undefiniert'
    
    items = json.loads(order[3])
    formated = ''
    for item in items:
        formated += str(items[item]) + ' ' + str(item) + '<br>'
    order[3] = formated

    return order

# This page will have the sign up form
@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        name = request.form['name']
        pw = request.form['password']

        if name == 'urs' and pw == 'sandra':
            session.permanent = True
            session['name'] = name
            return redirect(url_for('abrechnung'))
    else:
        pass
    return render_template('login.html')

# This page will be the page after the form
@app.route('/abrechnung', methods=['POST', 'GET'])
def abrechnung():
    global base_cash
    global revenue
    global cash_now
    global date

    if 'name' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        data = request.data.decode()
        app.logger.debug('Data recived: %s', data)
        json_object = json.loads(data)

        if 'base_cash' in json_object:
            base_cash = float(json_object['base_cash'])
            sql_db.set_base_cash(base_cash)
        
        if 'date' in json_object:
            date = json_object['date']

    calc_cash(date)
    product_sales = sql_db.count_todays_sales(date)
    weather = get_local_weather('schwyz')

    return render_template('admin.html', base_cash=base_cash, revenue=revenue, sales=sales, cash_now=cash_now, product_sales=product_sales, date=date, weather=weather)

@app.route('/produkte', methods=['POST', 'GET'])
def produkte():
    if 'name' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        data = request.data.decode()
        app.logger.debug('Data recived: %s', data)
        json_object = json.loads(data)

        if len(json_object) == 1:
            sql_db.delete_product(json_object[0])
        elif len(json_object) == 2:
            sql_db.update_product(json_object)
        elif len(json_object) == 4:
            sql_db.insert_product(json_object[0], json_object[1], json_object[2])

    time.sleep(0.2)
    products = sql_db.get_all_products_complete()
    
    return render_template('produkte.html', products=products)

@app.route('/statistik', methods=['POST', 'GET'])
def statistik():
    global date

    if request.method == 'POST':
        data = request.data.decode()
        app.logger.debug('Data recived: %s', data)
        json_object = json.loads(data)
        
        if 'date' in json_object:
            date = json_object['date']


    data = sql_db.get_data_sales_time(date)
    
    app.logger.debug(data)
    
    return render_template('statistik.html', date=date, python_data=data)

@app.route('/uploads/<path:filename>', methods=['GET', 'POST'])
def download(filename):

    if request.method == 'GET':
        app.logger.debug('get')

    full_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    app.logger.debug(full_path)

    if 'abrechnung' in filename:
        filename = 'abrechnung_' + datetime.now().strftime('%Y-%m-%d') + '.txt'
        generate_invoice(full_path + '/' + filename)
    return send_from_directory(full_path, filename)

def generate_invoice(filename):
    global base_cash
    global revenue
    global cash_now

    date = datetime.now().strftime('%Y-%m-%d')
    
    with open(filename, 'w') as f:
        f.write('Abrechnung Hundehalter Bistro ' + date + '\n')
        f.write('Kasse Grundstock: CHF ' + str(base_cash) + '\n')
        f.write('Einnahmen Bar: CHF ' + str(revenue[CASH]) + '\n')
        f.write('Kasseninhalt: CHF ' + str(cash_now) + '\n')
        f.write('Einnahmen Karte: CHF ' + str(revenue[CARD]) + '\n')
        f.write('Einnahmen TWINT: CHF ' + str(revenue[TWINT]) + '\n')
        f.write('Kosten Helfer: CHF ' + str(revenue[STAFF]) + '\n')
        f.write('Tageseinnahmen: CHF ' + str(revenue[0] + revenue[1] + revenue[2]) + '\n')
        f.write('\n')
        f.write('Anzahl Produkte:' + '\n')
        product_sales = sql_db.count_todays_sales()
        for prod in product_sales:
            f.write(f'{prod}: {product_sales[prod]}\n')
        f.write('\n')
        f.write('Bestellungen:' + '\n')
        orders = sql_db.get_todays_orders()
        orders = list(map(lambda o:format_order(o), orders))
        for order in orders:
            f.write(str(order) + '\n')

@app.route('/logout')
def logout():
    session.pop('name', None)
    return redirect(url_for('login'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error_404.html'), 404

# try to fix prblem with sending order id to page and back by disabling cache
@app.after_request
def add_header(r):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
