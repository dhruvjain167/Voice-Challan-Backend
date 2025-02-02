import os
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from fpdf import FPDF
from datetime import datetime
import json
import logging
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Neon database connection
NEON_DB_URL = os.getenv("DATABASE_URL")  # Format: postgres://user:password@host:port/database

def get_db_connection():
    """Create a new database connection to Neon database."""
    return psycopg2.connect(NEON_DB_URL)

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

@app.route('/')
def root():
    return jsonify({
        "status": "online",
        "message": "Voice Challan API is running"
    })

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
            quantity = item.get('quantity', 0)
            description = item.get('description', '')
            price = item.get('price', 0)
            item_total = quantity * price
            
            pdf.cell(30, 10, str(quantity), 1, 0, "C")
            pdf.cell(80, 10, description, 1, 0, "L")
            pdf.cell(30, 10, f"Rs {price:.2f}", 1, 0, "R")
            pdf.cell(30, 10, f"Rs {item_total:.2f}", 1, 1, "R")
            
            total_items += quantity
            total_price += item_total
        
        pdf.set_font("Helvetica", 'B', 10)
        pdf.cell(140, 10, "Total", 1, 0, "R")
        pdf.cell(30, 10, f"Rs {total_price:.2f}", 1, 1, "R")
        
        pdf_content = pdf.output(dest='S').encode('latin1')
        
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
        search = request.args.get('search', '')
        sort = request.args.get('sort', 'created_at')
        order = request.args.get('order', 'DESC')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')

        conn = get_db_connection()
        query = '''
            SELECT 
                id, 
                customer_name, 
                challan_no, 
                created_at, 
                items, 
                total_items, 
                total_price, 
                is_deleted
            FROM challans 
            WHERE is_deleted = false
        '''
        params = []

        if search:
            query += """ AND (
                customer_name ILIKE %s 
                OR challan_no::text ILIKE %s
            )"""
            search_pattern = f'%{search}%'
            params.extend([search_pattern, search_pattern])

        if start_date:
            query += " AND DATE(created_at) >= %s"
            params.append(start_date)
        if end_date:
            query += " AND DATE(created_at) <= %s"
            params.append(end_date)

        if sort in ['created_at', 'customer_name', 'challan_no', 'total_price']:
            order = 'DESC' if order.upper() == 'DESC' else 'ASC'
            query += f" ORDER BY {sort} {order}"

        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query, params)
            challans = cursor.fetchall()
            
        conn.close()

        formatted_challans = []
        for challan in challans:
            challan_dict = dict(challan)
            challan_dict['created_at'] = challan_dict['created_at'].isoformat()
            if isinstance(challan_dict['items'], str):
                challan_dict['items'] = json.loads(challan_dict['items'])
            formatted_challans.append(challan_dict)

        return jsonify(formatted_challans)

    except Exception as e:
        logger.error(f"Error listing challans: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-pdf/<int:challan_id>', methods=['GET'])
def download_pdf(challan_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute('SELECT pdf_data, challan_no FROM challans WHERE id = %s', (challan_id,))
            result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({'error': 'PDF not found'}), 404
        
        pdf_data, challan_no = result
        
        if isinstance(pdf_data, memoryview):
            pdf_data = pdf_data.tobytes()
        
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=challan_{challan_no}.pdf'
        return response
    
    except Exception as e:
        logger.error(f"Error downloading PDF: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)