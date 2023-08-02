from sql_db import *

def reset_app():
    create_DB()
    drop_products()
    create_DB()
    load_product_csv('preisliste.csv')

if __name__ == '__main__':
    reset_app()