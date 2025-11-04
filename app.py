from flask import Flask, render_template, request, jsonify, Response
import sqlite3
from datetime import datetime
import io
import csv

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('expenses.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  description TEXT NOT NULL,
                  amount REAL NOT NULL,
                  type TEXT NOT NULL,
                  category TEXT NOT NULL,
                  date TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    conn = sqlite3.connect('expenses.db')
    c = conn.cursor()
    c.execute('SELECT * FROM transactions ORDER BY date DESC')
    transactions = []
    for row in c.fetchall():
        transactions.append({
            'id': row[0],
            'description': row[1],
            'amount': row[2],
            'type': row[3],
            'category': row[4],
            'date': row[5]
        })
    conn.close()
    return jsonify(transactions)

@app.route('/api/transactions', methods=['POST'])
def add_transaction():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400

    # Basic validation
    description = data.get('description')
    amount = data.get('amount')
    ttype = data.get('type')
    category = data.get('category')
    date = data.get('date')

    if not description or amount is None or not ttype or not date:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    # ensure amount is a number
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid amount'}), 400

    conn = sqlite3.connect('expenses.db')
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO transactions (description, amount, type, category, date)
                     VALUES (?, ?, ?, ?, ?)''',
                  (description, amount, ttype, category or '', date))
        conn.commit()
        transaction_id = c.lastrowid
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        conn.close()

    return jsonify({'id': transaction_id, 'success': True})

@app.route('/api/transactions/<int:id>', methods=['DELETE'])
def delete_transaction(id):
    conn = sqlite3.connect('expenses.db')
    c = conn.cursor()
    c.execute('DELETE FROM transactions WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/statistics/<month>', methods=['GET'])
def get_statistics(month):
    conn = sqlite3.connect('expenses.db')
    c = conn.cursor()
    
    c.execute('''SELECT type, SUM(amount) FROM transactions 
                 WHERE date LIKE ? GROUP BY type''', (f'{month}%',))
    totals = {'income': 0, 'expense': 0}
    for row in c.fetchall():
        totals[row[0]] = row[1]
    
    c.execute('''SELECT category, SUM(amount) FROM transactions 
                 WHERE type = "expense" AND date LIKE ? 
                 GROUP BY category''', (f'{month}%',))
    categories = [{'name': row[0], 'value': row[1]} for row in c.fetchall()]
    
    c.execute('''SELECT date, SUM(amount) FROM transactions 
                 WHERE type = "expense" AND date LIKE ? 
                 GROUP BY date ORDER BY date''', (f'{month}%',))
    daily = [{'date': row[0], 'amount': row[1]} for row in c.fetchall()]
    
    c.execute('''SELECT substr(date, 1, 7) as month, type, SUM(amount) 
                 FROM transactions GROUP BY month, type ORDER BY month''')
    monthly = {}
    for row in c.fetchall():
        if row[0] not in monthly:
            monthly[row[0]] = {'month': row[0], 'income': 0, 'expense': 0}
        monthly[row[0]][row[1]] = row[2]
    
    conn.close()
    return jsonify({
        'totals': totals,
        'categories': categories,
        'daily': daily,
        'monthly': list(monthly.values())
    })


@app.route('/download/csv', methods=['GET'])
def download_csv():
    """Return transactions and summary as a CSV file. Optional query param `month` filters by YYYY-MM."""
    month = request.args.get('month')
    single = request.args.get('single', '0').lower() in ('1', 'true', 'yes')

    conn = sqlite3.connect('expenses.db')
    c = conn.cursor()

    # allow ordering via query param: 'asc' (oldest first) default, or 'desc'
    order = request.args.get('order', 'asc').lower()
    order_clause = 'DESC' if order == 'desc' else 'ASC'

    if month:
        tx_query = f'SELECT id, description, amount, type, category, date FROM transactions WHERE date LIKE ? ORDER BY date {order_clause}'
        tx_params = (f'{month}%',)
        totals_query = 'SELECT type, SUM(amount) FROM transactions WHERE date LIKE ? GROUP BY type'
        totals_params = (f'{month}%',)
        filename = f'transactions_{month}.csv'
    else:
        tx_query = f'SELECT id, description, amount, type, category, date FROM transactions ORDER BY date {order_clause}'
        tx_params = ()
        totals_query = 'SELECT type, SUM(amount) FROM transactions GROUP BY type'
        totals_params = ()
        filename = 'transactions_all.csv'

    c.execute(tx_query, tx_params)
    transactions = c.fetchall()

    c.execute(totals_query, totals_params)
    totals_rows = c.fetchall()

    totals = {'income': 0.0, 'expense': 0.0}
    for row in totals_rows:
        ttype = row[0]
        amount = row[1] or 0.0
        if ttype in totals:
            totals[ttype] = amount
        else:
            # unexpected type, store under its own key
            totals[ttype] = amount

    conn.close()

    # Build CSV in memory with summary combined column-wise
    output = io.StringIO()
    writer = csv.writer(output)

    balance = totals.get('income', 0.0) - totals.get('expense', 0.0)

    if single:
        # Single-column CSV: each row is a combined human-readable string
        writer.writerow(['Data'])

        # Summary row
        summary_line = f"Total Income: {totals.get('income', 0.0):.2f} | Total Expense: {totals.get('expense', 0.0):.2f} | Balance: {balance:.2f}"
        writer.writerow([summary_line])
        writer.writerow([''])
        # Transactions
        if transactions:
            for tx in transactions:
                # tx is (id, description, amount, type, category, date)
                line = f"ID:{tx[0]} | {tx[1]} | {tx[3].capitalize()} {tx[2]:.2f} | Category: {tx[4]} | Date: {tx[5]}"
                writer.writerow([line])
        else:
            writer.writerow(['No transactions'])
    else:
        # Combined header: transaction columns + summary columns
        header = ['ID', 'Description', 'Amount', 'Type', 'Category', 'Date',
                  'Total Income', 'Total Expense', 'Balance']
        writer.writerow(header)

        # Summary row: leave transaction columns empty, totals in the summary columns
        writer.writerow([
            '',  # ID
            '',  # Description
            '',  # Amount
            '',  # Type
            '',  # Category
            '',  # Date
            f'{totals.get("income", 0.0):.2f}',
            f'{totals.get("expense", 0.0):.2f}',
            f'{balance:.2f}'
        ])

        # Write transaction rows (transactions fill the first 6 columns, leave summary columns empty)
        if transactions:
            for tx in transactions:
                # tx is (id, description, amount, type, category, date)
                row = [tx[0], tx[1], f'{tx[2]:.2f}', tx[3], tx[4], tx[5], '', '', '']
                writer.writerow(row)
        else:
            # No transactions: write a single info row in the Description column
            writer.writerow(['', 'No transactions', '', '', '', '', f'{totals.get("income", 0.0):.2f}', f'{totals.get("expense", 0.0):.2f}', f'{balance:.2f}'])

    csv_data = output.getvalue()
    output.close()

    # Return response with CSV attachment
    resp = Response(csv_data, mimetype='text/csv')
    resp.headers.set('Content-Disposition', 'attachment', filename=filename)
    return resp
    

if __name__ == '__main__':
    app.run(debug=True)