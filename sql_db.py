from copy import copy
import csv
import json
import sqlite3
import os.path
import datetime
import numpy as np
import logging
from collections import Counter
from unittest import case

# sqllite läuft typischerweise auf gleicher maschine wie die anwendung
# mysql läuft typischerweise auf einer eigenen maschiene und die anwendung stellt eine verbindung her, skalliert besser
# todo: bei insert product automatisch delete product

# products
# | NAME | price | cathegory | active |
# =>
# | ID | name | price | color | active |
# wenn produkt verändert wird, wird im hintergrund ein neues produkt erstellt altes wird  DEFINITIV deaktiviert
# DB sollte im griff haben, welche produkte eigentlich das gleiche sind 

# setup logging
logger = logging.getLogger('sql')
f_handler = logging.FileHandler('app.log')
formater = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
f_handler.setFormatter(formater)
logger.setLevel(logging.DEBUG)
logger.addHandler(f_handler)
logger.info('sql_db called')

# Paymentmethods
CASH = 0
CARD = 1
TWINT = 2
STAFF = 3

# Special sales positions
TOYS = 0
TREATS = 1

def create_DB():
    try:
        with sqlite3.connect('hundehalter-bistro.db') as con:
            cursor = con.cursor()
            cursor.execute("""CREATE TABLE orders
                      (id INTEGER PRIMARY KEY, 
                      datetime TEXT, 
                      payment INTEGER,
                      items TEXT)""")
    except Exception as e:
        logger.error('Table "orders" not created', exc_info=True)
    
    try:
        with sqlite3.connect('hundehalter-bistro.db') as con:
            cursor = con.cursor()
            cursor.execute("""CREATE TABLE products
                      (id INTEGER PRIMARY KEY,
                      name TEXT, 
                      price REAL,
                      color TEXT,
                      active INTEGER)""")
    except Exception as e:
        logger.error('Table "products" not created', exc_info=True)
    
    try:
        with sqlite3.connect('hundehalter-bistro.db') as con:
            cursor = con.cursor()
            cursor.execute("""CREATE TABLE persdata
                      (name TEXT PRIMARY KEY, 
                      value REAL)""")
            cursor.execute('INSERT INTO persdata VALUES(?, ?)', ('base_cash', 0.0))
    except Exception as e:
        logger.error('Table "persdata" not created', exc_info=True)
    
    logger.info('DB table setup complete')

def drop_orders():
    with sqlite3.connect('hundehalter-bistro.db') as con:
        cursor = con.cursor()
        cursor.execute("DROP TABLE orders")
        logger.debug('table orders dropped')

def drop_products():
    with sqlite3.connect('hundehalter-bistro.db') as con:
        try:
            cursor = con.cursor()
            cursor.execute("DROP TABLE products")
            logger.debug('table products dropped')
        except Exception as e:
            logger.error('Could not delete table products', exc_info=True)

def get_base_cash():
    sql = f"SELECT value FROM persdata WHERE name = 'base_cash'"
    with sqlite3.connect('hundehalter-bistro.db') as con:
        cursor = con.cursor()
        result = cursor.execute(sql)
        value = result.fetchone()
        if value is not None:
            logger.debug('return base_cash ', value[0])
            return float(value[0])
        else:
            return 0.0

def set_base_cash(value):
    try:
        with sqlite3.connect('hundehalter-bistro.db') as con:
            cursor = con.cursor()
            cursor.execute(f"UPDATE persdata SET value={value} WHERE name = 'base_cash'")
    except Exception as e:
        logger.error('Exception while setting base cash', exc_info=True)

def insert_order(id:int, payment:int, items:list):
    dt = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    items = json.dumps(items)

    try:
        with sqlite3.connect('hundehalter-bistro.db') as con:
            cursor = con.cursor()
            cursor.execute('INSERT INTO orders(datetime, payment, items) VALUES(?, ?, ?)', (dt, payment, items))
    except sqlite3.IntegrityError:
        logger.warning('Entry in ordes already exists')

def insert_product(name:str, price:float, color:str):
    try:
        with sqlite3.connect('hundehalter-bistro.db') as con:
            cursor = con.cursor()
            cursor.execute('INSERT INTO products(name, price, color, active) VALUES(?, ?, ?, ?)', (name, price, color, 1))
    except Exception as e:
        logger.error('Product may already exist', exc_info=True)

"""
Adds Products from CSV file to DB
returns dict{name: price}
"""
def load_product_csv(path):
    products = {}
    with open(path, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            name, price, cathegory = row
            insert_product(name, price, cathegory)
            products[name] = float(price)
    return products

def get_todays_orders(date=None, n=None):
    orders = []
    if date == None:
        date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    if n:
        sql = f"SELECT * FROM orders WHERE datetime BETWEEN '{date} 00:00:00' AND '{date} 23:59:59' ORDER BY datetime DESC LIMIT {n}"
    else:
        sql = f"SELECT * FROM orders WHERE datetime BETWEEN '{date} 00:00:00' AND '{date} 23:59:59' ORDER BY datetime DESC"
    with sqlite3.connect('hundehalter-bistro.db') as con:
        cursor = con.cursor()
        results = cursor.execute(sql)
        for res in results:
            orders.append(res)
    return orders

def count_todays_sales(date=None, n=None):
    orders = get_todays_orders(date, n)
    products = get_all_products()

    counter = {}
    for prod in products:
        counter[prod] = 0

    for order in orders:
        ord = json.loads(order[3])
        
        if type(ord) != dict:
            continue
        
        for prod in ord:
            if prod in counter:
                counter[prod] += ord[prod]
            else:
                counter[prod] = ord[prod]
    return counter

def add_dict_counter(d1, d2):
    Cdict = Counter(d1) + Counter(d2)
    return(dict(Cdict))

'''
get sales data grouped in 15min slots
'''
def get_data_sales_time(date=None, product=None):
    # generate time vector
    year, month, day = [int(n) for n in date.split('-')] 
    base = datetime.datetime(year, month, day, 6)
    time_vector = np.array([base + datetime.timedelta(minutes=15*i) for i in range(56)])

    orders = get_todays_orders(date)
    order_time = []
    products = []
    for order in orders:
        prods = json.loads(order[3])
        if type(prods) == dict:
            products.append(prods)
            order_time.append(datetime.datetime.strptime(order[1], '%Y-%m-%d %H:%M:%S'))

    product_counter = [{}] * len(time_vector) 
    for order_t, p in zip(order_time, products):
        for i in range(len(time_vector)):
            if order_t < time_vector[i]:
                product_counter[i] = add_dict_counter(product_counter[i], p)
                break
    
    time_vector = list(map(lambda x: x.strftime('%H:%M:%S'), time_vector))

    out_list = []
    for x, y in zip(time_vector, product_counter):
        if product:
            out_list.append({'x': x, 'y': y[product] if product in y else 0})
        else:
            out_list.append({'x': x, 'y': sum(y.values())})

    return out_list

'''
gets price from DB based on product name
'''
def get_product_price(name:str):
    sql = f"SELECT price FROM products WHERE name = '{name}'"
    with sqlite3.connect('hundehalter-bistro.db') as con:
        cursor = con.cursor()
        result = cursor.execute(sql)
        price = result.fetchone()
        if price is not None:
            return price[0]
        else:
            return 0

'''
returns all products in DB as list[name]
'''
def get_all_products():
    prods = []
    sql = f"SELECT name FROM products WHERE active == 1"
    with sqlite3.connect('hundehalter-bistro.db') as con:
        cursor = con.cursor()
        results = cursor.execute(sql)
        for res in results:
            prods.append(res[0])
    return prods

'''
returns all products in DB as dict{name: price}
'''
def get_all_products_dict():
    prods = {}
    sql = f"SELECT name, price FROM products WHERE active >= 1 ORDER BY active"
    with sqlite3.connect('hundehalter-bistro.db') as con:
        cursor = con.cursor()
        results = cursor.execute(sql)
        for res in results:
            prods[res[0]] = res[1]
    return prods

'''
returns all products in DB as list[id, name, price, color, active]
'''
def get_all_products_complete():
    prods = []
    sql = f"SELECT * FROM products"
    with sqlite3.connect('hundehalter-bistro.db') as con:
        cursor = con.cursor()
        results = cursor.execute(sql)
        for res in results:
            prods.append(list(res))
    
    for i in range(len(prods)):
        prods[i][3] = format_color(prods[i][3])

    return prods

def update_product(data):
    id_column, value = data
    prod_id, column = id_column.split('_')
    logger.info(f'updating product ID: {prod_id} column: {column} value: {value}')
    
    if column == 'color':
        value = value.replace('#', '0x')
        value = int(value, 16)
    
    try:
        with sqlite3.connect('hundehalter-bistro.db') as con:
            cursor = con.cursor()
            if type(value) == str:
                sql = f"UPDATE products SET {column} = '{value}' WHERE id == {prod_id}"
            else:
                sql = f"UPDATE products SET {column} = {value} WHERE id == {prod_id}"
            logger.debug(sql)
            cursor.execute(sql)
    except Exception as e:
        print('Exception:', e)

def delete_product(data):
    prod_id, code = data.split('_')

    if code != 'delete':
        return 0
    
    try:
        with sqlite3.connect('hundehalter-bistro.db') as con:
            cursor = con.cursor()
            cursor.execute(f"DELETE FROM products WHERE id == {prod_id}")
    except Exception as e:
        logger.error('Exception durring deletion of product', exc_info=True)

def calc_todays_revenue(date=None):
    revenue = [0.0, 0.0, 0.0, 0.0]
    sales = [0.0 , 0.0]
    products = get_all_products()

    orders = get_todays_orders(date)
    # break every order down, add the revenue corresponding to paymentmethod and keep track of special sales
    for order in orders:
        items = json.loads(order[3])
        list = [get_product_price(item) * items[item] for item in items] # for every item in the order calc price * count
        list_toys = [parse_price_in_name(item, 'Hundespielzeug') * items[item] for item in items if item not in products]
        list_treats = [parse_price_in_name(item, 'Hundegudi') * items[item] for item in items if item not in products]
        rev = sum(list) + sum(list_toys) + sum(list_treats)

        payment_method = order[2]
        revenue[payment_method] += rev
        
        sales[0] += sum(list_toys)
        sales[1] += sum(list_treats)
    
    return revenue, sales

'''
Products with price 0 have their price within the product name.
This function returns the price based on the product name
Format: name(price)
'''
def parse_price_in_name(product, type):
    price = product[product.find('(')+1:product.find(')')]
    if type in product:
        price = float(price)
    else:
        price = 0.0
    return price

'''
Returns largest order id in DB +1
'''
def get_new_order_id():
    sql = "SELECT id FROM orders ORDER BY id DESC LIMIT 1"
    with sqlite3.connect('hundehalter-bistro.db') as con:
        cursor = con.cursor()
        result = cursor.execute(sql)
        id = result.fetchone()
    if id is not None:
        new_id = id[0] + 1
    else:
        new_id = 0
    return new_id

def get_products():
    sql = "SELECT * FROM products"
    with sqlite3.connect('hundehalter-bistro.db') as con:
        cursor = con.cursor()
        results = cursor.execute(sql)
        products = [product for product in results]
    return products

def format_color(color):
    color = hex(int(color))
    color = color.replace('0x', '#')
    color = color[:1] + '0' + color[1:] if len(color) == 6 else color
    return color

def get_colors_dict():
    colors = {}
    sql = "SELECT name, color FROM products"
    with sqlite3.connect('hundehalter-bistro.db') as con:
        cursor = con.cursor()
        results = cursor.execute(sql)
        for res in results:
            prod = res[0]
            color = res[1]
            colors[prod] = format_color(color)
    return colors

def create_dict():
    with open('project/preisliste.csv', 'r') as file:
        reader = csv.reader(file)
        products = {}
        for row in reader:
            k, v = row
            products[k] = float(v)
    return products

def save_order_history(order_history: list):
    file_name = 'project/bestellungen_' + str(datetime.date.today()) + '.csv'
    
    with open(file_name, 'w') as file:
        for order in order_history:
            file.write(','.join(order))
            file.write('\n')

def load_order_history():
    file_name = 'project/bestellungen_' + str(datetime.date.today()) + '.csv'

    order_history = []
    if os.path.exists(file_name):
        with open(file_name, 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                order_history.append(row)
        
    return order_history

def save_invoice(sold_products: dict, total: float):
    file_name = 'project/abrechnung_' + str(datetime.date.today()) + '.csv'

    with open(file_name, 'w') as file:
        for key in sold_products:
            line = str(key) + ',' + str(sold_products[key]) + '\n'
            file.write(line)
        file.write('Total CHF,' + str(total))

def load_invoice(products):
    file_name = 'project/abrechnung_' + str(datetime.date.today()) + '.csv'

    if os.path.exists(file_name):
        lines = []
        with open(file_name, 'r') as file:
            for line in file:
                lines.append(line)
    
        total = lines.pop(-1)
        total = float(total.split(',')[1])

        for i in range(len(lines)):
            lines[i] = lines[i][0:-1].split(',')

        lines_dict = {}
        for element in lines:
            lines_dict[element[0]] = element[1]

        for key in products:
            products[key] = int(lines_dict[key])
    else:
        for key in products:
            products[key] = 0

    return products

if __name__ == '__main__':
    drop_products()
    create_DB()
    load_product_csv('project/preisliste.csv')

    print(get_colors_dict())
