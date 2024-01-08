#!/usr/bin/python3

import pandas as pd
import sqlite3

db = sqlite3.connect('cas_eresearch_gitlab_app.db')
cursor = db.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
for table_name in tables:
    table_name = table_name[0]
    table = pd.read_sql_query("SELECT * from %s" % table_name, db)
    table.to_csv(f'{table_name}.tsv', index_label='index',sep='\t')
    with open(f'{table_name}.tsv','r') as file:
        for i_line,line in enumerate(file.readlines()):
            print(line)

cursor.close()
db.close()

