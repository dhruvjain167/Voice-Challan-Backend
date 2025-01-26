# from flask import Flask, request, send_file, jsonify, make_response
# from flask_cors import CORS
# from fpdf import FPDF
# import os
# import sqlite3
# from datetime import datetime
# import json
# import logging

# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)

# app = Flask(__name__)
# CORS(app, resources={
#     r"/api/*": {
#         "origins": [
#             "http://localhost:5173",  # Local development
#             "https://voice-challan-app.vercel.app",  # Deployed frontend URL
#             "*"  # Wildcard for flexibility (use cautiously)
#         ],
#         "methods": ["GET", "POST", "OPTIONS"],
#         "allow_headers": ["Content-Type", "Authorization"]
#     }
# })

# PDF_DIR = "generated_pdfs"
# BACKUP_DIR = "backups"

# # Create directories if they don't exist
# for directory in [PDF_DIR, BACKUP_DIR]:
#     if not os.path.exists(directory):
#         os.makedirs(directory)

# def init_db():
#     conn = sqlite3.connect('challans.db')
#     c = conn.cursor()
#     c.execute('''
#         CREATE TABLE IF NOT EXISTS challans (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             customer_name TEXT NOT NULL,
#             challan_no TEXT NOT NULL UNIQUE,
#             pdf_path TEXT NOT NULL,
#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#             items TEXT NOT NULL,
#             total_items INTEGER NOT NULL,
#             total_price REAL DEFAULT 0,
#             is_deleted BOOLEAN DEFAULT 0
#         )
#     ''')
#     conn.commit()
#     conn.close()

# # Initialize database
# init_db()

# @app.route('/api/generate-pdf', methods=['POST', 'OPTIONS'])
# def generate_pdf():
#     # Handle preflight OPTIONS request
#     if request.method == 'OPTIONS':
#         response = make_response()
#         response.headers.add("Access-Control-Allow-Origin", "*")
#         response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
#         response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
#         return response
    
#     try:
#         # Validate JSON content
#         if not request.is_json:
#             return jsonify({'error': 'Content-Type must be application/json'}), 400
        
#         data = request.json
        
#         # Validate required fields
#         required_fields = ['items', 'customerName', 'challanNo']
#         missing_fields = [field for field in required_fields if field not in data]
        
#         if missing_fields:
#             return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
#         items = data['items']
#         if not isinstance(items, list) or not items:
#             return jsonify({'error': 'Items must be a non-empty array'}), 400
        
#         # Validate item structure
#         for idx, item in enumerate(items):
#             if not isinstance(item, dict) or 'quantity' not in item or 'description' not in item:
#                 return jsonify({'error': f'Invalid item at index {idx}. Each item must have quantity and description'}), 400
        
#         customer_name = data['customerName']
#         challan_no = data['challanNo']
        
#         # Generate safe filename
#         current_date = datetime.now().strftime('%Y%m%d')
#         safe_customer_name = "".join(x for x in customer_name if x.isalnum() or x in [' ', '_']).strip()
#         filename = f"{safe_customer_name}_{current_date}_challan_{challan_no}.pdf"
#         filepath = os.path.join(PDF_DIR, filename)

#         # Create PDF
#         pdf = FPDF()
#         pdf.add_page()
#         pdf.set_font("Helvetica", '', 12)
        
#         # PDF Header
#         pdf.cell(200, 10, txt="Shakti Trading Co.", ln=True, align="C")
#         pdf.cell(200, 10, txt=f"Date: {datetime.now().strftime('%d-%m-%Y')}", ln=True, align="R")
#         pdf.cell(200, 10, txt=f"Customer: {customer_name}", ln=True, align="L")
#         pdf.cell(200, 10, txt=f"Challan No: {challan_no}", ln=True, align="L")
        
#         # Table Headers
#         pdf.set_font("Helvetica", 'B', 10)
#         pdf.cell(30, 10, "Quantity", 1, 0, "C")
#         pdf.cell(80, 10, "Description", 1, 0, "C")
#         pdf.cell(30, 10, "Price", 1, 0, "C")
#         pdf.cell(30, 10, "Total", 1, 1, "C")
        
#         # Table Data
#         pdf.set_font("Helvetica", '', 10)
#         total_items = 0
#         total_price = 0
        
#         for item in items:
#             quantity = item['quantity']
#             price = item.get('price', 0)
#             item_total = quantity * price
            
#             pdf.cell(30, 10, str(quantity), 1, 0, "C")
#             pdf.cell(80, 10, item['description'], 1, 0, "L")
#             pdf.cell(30, 10, f"Rs {price:.2f}", 1, 0, "R")
#             pdf.cell(30, 10, f"Rs {item_total:.2f}", 1, 1, "R")
            
#             total_items += quantity
#             total_price += item_total
        
#         # Total Row
#         pdf.set_font("Helvetica", 'B', 10)
#         pdf.cell(140, 10, "Total", 1, 0, "R")
#         pdf.cell(30, 10, f"Rs {total_price:.2f}", 1, 1, "R")
        
#         # Save PDF
#         pdf.output(filepath)
        
#         # Database Insertion
#         try:
#             conn = sqlite3.connect('challans.db')
#             c = conn.cursor()
#             c.execute('''
#                 INSERT INTO challans (customer_name, challan_no, pdf_path, items, total_items, total_price)
#                 VALUES (?, ?, ?, ?, ?, ?)
#             ''', (customer_name, challan_no, filepath, json.dumps(items), total_items, total_price))
#             conn.commit()
#         except sqlite3.IntegrityError:
#             return jsonify({'error': 'Challan number already exists'}), 400
#         except Exception as e:
#             return jsonify({'error': str(e)}), 500
#         finally:
#             conn.close()
        
#         # Return PDF
#         return send_file(filepath, as_attachment=True, download_name=filename)
        
#     except Exception as e:
#         logger.error(f"Unexpected error: {str(e)}")
#         return jsonify({'error': str(e)}), 500

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000, debug=True)

import os
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from fpdf import FPDF
from datetime import datetime
import json
import logging
import psycopg2
from psycopg2.extras import DictCursor
import base64

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "http://localhost:5173",
            "https://your-frontend-url.vercel.app",
            "*"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

def get_db_connection():
    """Create a database connection using Supabase PostgreSQL credentials"""
    return psycopg2.connect(
        dbname=os.environ.get('SUPABASE_DB_NAME'),
        user=os.environ.get('SUPABASE_USER'),
        password=os.environ.get('SUPABASE_PASSWORD'),
        host=os.environ.get('SUPABASE_HOST'),
        port=os.environ.get('SUPABASE_PORT', 5432)
    )

def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Create challans table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS challans (
                id SERIAL PRIMARY KEY,
                customer_name TEXT NOT NULL,
                challan_no TEXT NOT NULL UNIQUE,
                pdf_data BYTEA NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                items JSONB NOT NULL,
                total_items INTEGER NOT NULL,
                total_price REAL DEFAULT 0,
                is_deleted BOOLEAN DEFAULT false
            )
        ''')
        conn.commit()
    conn.close()

# Initialize database on startup
init_db()

@app.route('/api/generate-pdf', methods=['POST', 'OPTIONS'])
def generate_pdf():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response
    
    try:
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.json
        required_fields = ['items', 'customerName', 'challanNo']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        items = data['items']
        if not isinstance(items, list) or not items:
            return jsonify({'error': 'Items must be a non-empty array'}), 400
        
        for idx, item in enumerate(items):
            if not isinstance(item, dict) or 'quantity' not in item or 'description' not in item:
                return jsonify({'error': f'Invalid item at index {idx}. Each item must have quantity and description'}), 400
        
        customer_name = data['customerName']
        challan_no = data['challanNo']
        
        # Generate PDF in memory
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", '', 12)
        
        pdf.cell(200, 10, txt="Shakti Trading Co.", ln=True, align="C")
        pdf.cell(200, 10, txt=f"Date: {datetime.now().strftime('%d-%m-%Y')}", ln=True, align="R")
        pdf.cell(200, 10, txt=f"Customer: {customer_name}", ln=True, align="L")
        pdf.cell(200, 10, txt=f"Challan No: {challan_no}", ln=True, align="L")
        
        pdf.set_font("Helvetica", 'B', 10)
        pdf.cell(30, 10, "Quantity", 1, 0, "C")
        pdf.cell(80, 10, "Description", 1, 0, "C")
        pdf.cell(30, 10, "Price", 1, 0, "C")
        pdf.cell(30, 10, "Total", 1, 1, "C")
        
        pdf.set_font("Helvetica", '', 10)
        total_items = 0
        total_price = 0
        
        for item in items:
            quantity = item['quantity']
            price = item.get('price', 0)
            item_total = quantity * price
            
            pdf.cell(30, 10, str(quantity), 1, 0, "C")
            pdf.cell(80, 10, item['description'], 1, 0, "L")
            pdf.cell(30, 10, f"Rs {price:.2f}", 1, 0, "R")
            pdf.cell(30, 10, f"Rs {item_total:.2f}", 1, 1, "R")
            
            total_items += quantity
            total_price += item_total
        
        pdf.set_font("Helvetica", 'B', 10)
        pdf.cell(140, 10, "Total", 1, 0, "R")
        pdf.cell(30, 10, f"Rs {total_price:.2f}", 1, 1, "R")
        
        # Get PDF content as bytes
        pdf_content = pdf.output(dest='S').encode('latin1')
        
        # Store challan in PostgreSQL with PDF data
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO challans 
                (customer_name, challan_no, pdf_data, items, total_items, total_price)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (customer_name, challan_no, pdf_content, json.dumps(items), total_items, total_price))
            challan_id = cursor.fetchone()[0]
            conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'PDF generated successfully',
            'challanId': challan_id,
            'challanNo': challan_no
        })
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/list-challans', methods=['GET'])
def list_challans():
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            search_term = request.args.get('search', '')
            sort_by = request.args.get('sort', 'created_at')
            order = request.args.get('order', 'DESC')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            query = '''
                SELECT id, customer_name, challan_no, created_at, total_items, 
                       total_price
                FROM challans 
                WHERE is_deleted = false
            '''
            params = []
            
            if search_term:
                query += ' AND (customer_name ILIKE %s OR challan_no ILIKE %s)'
                search_param = f'%{search_term}%'
                params.extend([search_param, search_param])
            
            if start_date:
                query += ' AND created_at >= %s'
                params.append(start_date)
            if end_date:
                query += ' AND created_at <= %s'
                params.append(end_date)
            
            query += f' ORDER BY {sort_by} {order}'
            
            cursor.execute(query, params)
            challans = cursor.fetchall()
        
        return jsonify([dict(challan) for challan in challans])
    except Exception as e:
        logger.error(f"Error listing challans: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-pdf/<int:challan_id>', methods=['GET'])
def download_pdf(challan_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                'SELECT pdf_data, challan_no FROM challans WHERE id = %s', 
                (challan_id,)
            )
            result = cursor.fetchone()
        
        if not result:
            return jsonify({'error': 'PDF not found'}), 404
        
        pdf_data, challan_no = result
        
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=challan_{challan_no}.pdf'
        return response
    
    except Exception as e:
        logger.error(f"Error downloading PDF: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)


