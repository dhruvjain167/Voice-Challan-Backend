import os
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from fpdf import FPDF
from datetime import datetime
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import base64
from dotenv import load_dotenv
from contextlib import contextmanager
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch

# Load environment variables from .env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Replace Supabase connection with Neon connection manager
@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = psycopg2.connect(
            os.getenv('DATABASE_URL'),
            cursor_factory=RealDictCursor,
            sslmode='require'  # Neon requires SSL
        )
        yield conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

@app.route('/')
def root():
    return jsonify({
        "status": "online",
        "message": "Voice Challan API is running"
    })

@app.route('/api/generate-pdf', methods=['POST'])
def generate_pdf():
    try:
        data = request.json
        challan_no = data.get('challan_no')
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM challans 
                    WHERE challan_no = %s AND is_deleted = FALSE
                """, (challan_no,))
                challan = cur.fetchone()

                if not challan:
                    return jsonify({"error": "Challan not found"}), 404

                # Generate PDF
                pdf_buffer = generate_challan_pdf(challan)
                
                # Save PDF path in database
                pdf_path = f"challans/{challan_no}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
                
                cur.execute("""
                    UPDATE challans 
                    SET pdf_path = %s 
                    WHERE challan_no = %s
                """, (pdf_path, challan_no))
                conn.commit()
                
                response = make_response(pdf_buffer)
                response.headers['Content-Type'] = 'application/pdf'
                response.headers['Content-Disposition'] = f'attachment; filename=challan_{challan_no}.pdf'
                
                return response
    
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return jsonify({"error": str(e)}), 500

def generate_challan_pdf(challan_data):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4  # Standard A4 size
    
    # Parse items from JSON string
    items = json.loads(challan_data['items'])
    
    # Header
    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, height - 50, "Challan Receipt")
    
    # Customer and Challan Details
    p.setFont("Helvetica", 12)
    p.drawString(50, height - 100, f"Customer Name: {challan_data['customer_name']}")
    p.drawString(50, height - 120, f"Challan No: {challan_data['challan_no']}")
    p.drawString(50, height - 140, f"Date: {challan_data['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Items Table Header
    y_position = height - 180
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y_position, "Item")
    p.drawString(250, y_position, "Quantity")
    p.drawString(350, y_position, "Price")
    p.drawString(450, y_position, "Total")
    
    # Draw line under header
    y_position -= 15
    p.line(50, y_position, 550, y_position)
    
    # Items List
    y_position -= 25
    p.setFont("Helvetica", 10)
    
    for item in items:
        p.drawString(50, y_position, item.get('name', ''))
        p.drawString(250, y_position, str(item.get('quantity', '')))
        p.drawString(350, y_position, f"₹{item.get('price', 0):.2f}")
        item_total = float(item.get('price', 0)) * float(item.get('quantity', 0))
        p.drawString(450, y_position, f"₹{item_total:.2f}")
        y_position -= 20
    
    # Total Section
    y_position -= 20
    p.line(50, y_position, 550, y_position)
    y_position -= 20
    p.setFont("Helvetica-Bold", 12)
    p.drawString(350, y_position, "Total Items:")
    p.drawString(450, y_position, str(challan_data['total_items']))
    y_position -= 20
    p.drawString(350, y_position, "Total Amount:")
    p.drawString(450, y_position, f"₹{challan_data['total_price']:.2f}")
    
    # Footer
    p.setFont("Helvetica-Oblique", 8)
    p.drawString(50, 30, "Thank you for your business!")
    p.drawString(50, 15, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    p.save()
    pdf_value = buffer.getvalue()
    buffer.close()
    
    return pdf_value

# Add a route to get the PDF by challan number
@app.route('/api/challans/<challan_no>/pdf', methods=['GET'])
def get_challan_pdf(challan_no):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM challans 
                    WHERE challan_no = %s AND is_deleted = FALSE
                """, (challan_no,))
                challan = cur.fetchone()

                if not challan:
                    return jsonify({"error": "Challan not found"}), 404

                pdf_buffer = generate_challan_pdf(challan)
                
                response = make_response(pdf_buffer)
                response.headers['Content-Type'] = 'application/pdf'
                response.headers['Content-Disposition'] = f'attachment; filename=challan_{challan_no}.pdf'
                
                return response
                
    except Exception as e:
        logger.error(f"Error fetching PDF: {e}")
        return jsonify({"error": str(e)}), 500

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

        # Add search condition if search parameter is provided
        if search:
            query += """ AND (
                customer_name ILIKE %s 
                OR challan_no::text ILIKE %s
            )"""
            search_pattern = f'%{search}%'
            params.extend([search_pattern, search_pattern])

        # Add date range conditions if provided
        if start_date:
            query += " AND DATE(created_at) >= %s"
            params.append(start_date)
        if end_date:
            query += " AND DATE(created_at) <= %s"
            params.append(end_date)

        # Add sorting
        if sort in ['created_at', 'customer_name', 'challan_no', 'total_price']:
            order = 'DESC' if order.upper() == 'DESC' else 'ASC'
            query += f" ORDER BY {sort} {order}"

        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            challans = cursor.fetchall()
            
        conn.close()

        # Convert DictRow objects to regular dictionaries and format the data
        formatted_challans = []
        for challan in challans:
            challan_dict = dict(challan)
            # Convert datetime to ISO format string
            challan_dict['created_at'] = challan_dict['created_at'].isoformat()
            # Parse JSON string to dictionary if it's a string
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
        
        if not result:
            return jsonify({'error': 'PDF not found'}), 404
        
        pdf_data, challan_no = result
        
        # Convert memoryview to bytes
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
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
                return jsonify({"status": "healthy"}), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
