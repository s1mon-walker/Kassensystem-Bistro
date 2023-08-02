import csv
import os.path
import datetime

# sqllite läuft typischerweise auf gleicher maschine wie die anwendung
# mysql läuft typischerweise auf einer eigenen maschiene und die anwendung stellt eine verbindung her, skalliert besser

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
    products = create_dict()
    print(products)

    history = [['Bier', 'Bier'],['Bier']]
    counter = {'Bier':3}
    total = 15

    save_order_history(history)
    save_invoice(counter, total)

    print(load_order_history())
    print(load_invoice())
