from flask import Flask, render_template, request, jsonify
import os
from dispute_assistant import process_image, save_dispute_info
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configure upload folders
app.config['PERSONAL_FOLDER'] = 'personal_info'
app.config['CONTACT_FOLDER'] = 'contact_info'

# Ensure the upload folders exist
os.makedirs(app.config['PERSONAL_FOLDER'], exist_ok=True)
os.makedirs(app.config['CONTACT_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'})
    
    file = request.files['file']
    file_type = request.form.get('type')
    
    # 获取 Twilio 凭证
    twilio_sid = request.form.get('twilio_sid')
    twilio_token = request.form.get('twilio_token')
    twilio_from_number = request.form.get('twilio_from_number')
    twilio_to_number = request.form.get('twilio_to_number')
    
    if not all([twilio_sid, twilio_token, twilio_from_number, twilio_to_number]):
        return jsonify({'success': False, 'error': 'All Twilio credentials are required'})
    
    # 保存 Twilio 凭证到环境变量
    os.environ['TWILIO_ACCOUNT_SID'] = twilio_sid
    os.environ['TWILIO_AUTH_TOKEN'] = twilio_token
    os.environ['TWILIO_FROM_NUMBER'] = twilio_from_number
    os.environ['TWILIO_TO_NUMBER'] = twilio_to_number
    
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})
    
    if file and file_type:
        filename = secure_filename(file.filename)
        if file_type == 'personal':
            filepath = os.path.join(app.config['PERSONAL_FOLDER'], 'personal.png')
        else:
            filepath = os.path.join(app.config['CONTACT_FOLDER'], 'contact.png')
        
        file.save(filepath)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Invalid request'})

@app.route('/process', methods=['POST'])
def process_dispute():
    try:
        # Process personal info
        personal_path = os.path.join(app.config['PERSONAL_FOLDER'], 'personal.png')
        contact_path = os.path.join(app.config['CONTACT_FOLDER'], 'contact.png')
        
        if not (os.path.exists(personal_path) and os.path.exists(contact_path)):
            return jsonify({
                'success': False, 
                'error': 'Missing required files'
            })

        # Run the dispute assistant
        import dispute_assistant
        result = dispute_assistant.main()
        
        return jsonify({
            'success': True,
            'message': 'Dispute processed successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    app.run(debug=True) 