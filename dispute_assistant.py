#!/usr/bin/env python3

import pytesseract
from PIL import Image
import re
import os
import json
from collections import Counter
from twilio.rest import Client
import datetime
import subprocess
from voice_generator import generate_twiml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Twilio credentials
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_FROM_NUMBER = os.getenv('TWILIO_FROM_NUMBER')
TWILIO_TO_NUMBER = os.getenv('TWILIO_TO_NUMBER')

# Get personal information
MY_FIRST_NAME = os.getenv('MY_FIRST_NAME')
MY_LAST_NAME = os.getenv('MY_LAST_NAME')
MY_ETS_ID = os.getenv('MY_ETS_ID')
MY_EMAIL = os.getenv('MY_EMAIL')

def extract_text_from_image(image_path):
    """Extract text from image"""
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        return None

def extract_personal_info(text):
    """Extract personal information"""
    email = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    first_name = re.findall(r'First\s*/\s*Given\s*Name\s*(\w+)', text)
    last_name = re.findall(r'Last\s*/\s*Family\s*Name\s*(\w+)', text)
    ets_id = re.findall(r'ETS\s*ID:\s*([A-Z0-9]+)', text)
    
    return {
        "email": email[0] if email else None,
        "first_name": first_name[0] if first_name else None,
        "last_name": last_name[0] if last_name else None,
        "ets_id": ets_id[0] if ets_id else None
    }

def extract_contact_info(text):
    """Extract contact information"""
    # Extract email (support multiple formats)
    email_patterns = [
        r'[\w\.-]+@[\w\.-]+\.\w+',  # Basic email format
        r'Contact:?\s*([\w\.-]+@[\w\.-]+\.\w+)',  # With Contact label
        r'Email:?\s*([\w\.-]+@[\w\.-]+\.\w+)',    # With Email label
        r'Support:?\s*([\w\.-]+@[\w\.-]+\.\w+)'   # With Support label
    ]
    
    # Try all email patterns
    email = None
    for pattern in email_patterns:
        matches = re.findall(pattern, text)
        if matches:
            email = matches[0]
            break
    
    # Add debug information
    print(f"Debug: TWILIO_TO_NUMBER = {os.getenv('TWILIO_TO_NUMBER')}")
    
    return {
        "contact_email": email,
        "contact_phone": None  # Don't set phone number yet
    }

def categorize_dispute(text):
    """Categorize dispute content"""
    # Define keyword dictionary
    categories = {
        "ets_refund": [
            "refund", "test fee", "registration fee", "cancellation", "reschedule",
            "toefl", "ets", "test center", "exam fee", "payment", "reimbursement",
            "registration", "cancel", "postpone", "fee return"
        ],
        "ecommerce_refund": [
            "amazon", "ebay", "walmart", "best buy", "order", "product",
            "delivery", "item", "purchase", "return", "merchandise"
        ],
        "flight_claim": [
            "flight", "airline", "united", "delta", "southwest", "expedia",
            "ticket", "booking", "reservation", "delay", "cancellation", "travel"
        ],
        "credit_card": [
            "credit card", "chase", "amex", "wells fargo", "capital one",
            "transaction", "charge", "dispute", "unauthorized", "fraud"
        ],
        "shipping_claim": [
            "fedex", "usps", "ups", "dhl", "package", "delivery",
            "shipping", "lost", "damaged", "tracking", "parcel"
        ],
        "rideshare": [
            "uber", "lyft", "turo", "hertz", "ride", "driver",
            "trip", "car", "rental", "service", "pickup"
        ],
        "service_claim": [
            "service", "provider", "appointment", "subscription",
            "membership", "account", "access", "quality", "contract"
        ]
    }
    
    # Convert text to lowercase for matching
    text = text.lower()
    
    # Calculate matches for each category
    matches = {}
    for category, keywords in categories.items():
        count = sum(1 for keyword in keywords if keyword in text)
        matches[category] = count
    
    # Find the category with most matches
    if not any(matches.values()):
        return {
            "primary_category": "general",
            "confidence": 0,
            "all_matches": matches,
            "suggested_template": "general_dispute"
        }
    
    max_count = max(matches.values())
    primary_category = max(matches.items(), key=lambda x: x[1])[0]
    total_matches = sum(matches.values())
    
    # Calculate confidence
    confidence = (max_count / total_matches) if total_matches > 0 else 0
    
    # 根据类别选择模板
    template_mapping = {
        "ets_refund": "ets_refund_template",
        "ecommerce_refund": "ecommerce_refund_template",
        "flight_claim": "flight_claim_template",
        "credit_card": "credit_card_dispute_template",
        "shipping_claim": "shipping_claim_template",
        "rideshare": "rideshare_dispute_template",
        "service_claim": "service_claim_template"
    }
    
    return {
        "primary_category": primary_category,
        "confidence": round(confidence * 100, 2),
        "all_matches": matches,
        "suggested_template": template_mapping.get(primary_category, "general_dispute")
    }

def process_dispute(text):
    """Process dispute text and provide analysis"""
    # Extract basic information
    info = extract_personal_info(text)
    
    # Categorize dispute
    category_info = categorize_dispute(text)
    
    # Merge results
    result = {
        "personal_info": info,
        "dispute_category": category_info["primary_category"],
        "confidence": category_info["confidence"],
        "category_details": category_info["all_matches"]
    }
    
    return result

def save_dispute_info(info, filename="dispute_info.json"):
    """Save dispute information to file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=4)
        print(f"\nInformation saved to {filename}")
    except Exception as e:
        print(f"Error saving information: {str(e)}")

def process_image(image_path, info_type="personal"):
    """Process image and extract information"""
    if not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        return
        
    text = extract_text_from_image(image_path)
    if not text:
        return
    
    print(f"\nProcessing image: {os.path.basename(image_path)}")
    print("\nOriginal text:")
    print(text)
    
    if info_type == "personal":
        info = extract_personal_info(text)
        print("\nExtracted personal information:")
        dispute_info = process_dispute(text)
        print("\nDispute classification result:")
        print(f"Primary category: {dispute_info['dispute_category']}")
        print(f"Confidence: {dispute_info['confidence']}%")
        save_dispute_info(dispute_info)
    else:
        info = extract_contact_info(text)
        print("\nExtracted contact information:")
        
    for key, value in info.items():
        if value:
            print(f"{key}: {value}")

def generate_ets_dispute_template(info):
    """Generate ETS TOEFL Refund Dispute Template"""
    personal = info.get("personal", {})
    name = f"{personal.get('first_name', '')} {personal.get('last_name', '')}".strip()
    ets_id = personal.get('ets_id', '')
    email = personal.get('email', '')
    
    template = f"""
Subject: TOEFL Test Fee Refund Request - ETS ID: {ets_id}

Dear ETS Customer Service,

I am writing to request a refund for my TOEFL test registration. Below are my details:

Personal Information:
- Full Name: {name}
- ETS ID: {ets_id}
- Email Address: {email}

Reason for Refund Request:
I am requesting a refund for my TOEFL test registration due to [specific reason]. I registered for the test on [test registration date] and paid [amount] USD for the test fee.

Supporting Information:
1. I have not taken the test yet
2. The registration is still within the refund eligibility period
3. I have all necessary documentation to support my refund request

Actions Taken:
1. I have reviewed the ETS refund policy
2. I have gathered all required documentation
3. I am making this request within the specified timeframe

Request:
I kindly request a full refund of my test registration fee to be processed according to ETS refund policies.

Required Documents Attached:
1. Test Registration Confirmation
2. Payment Receipt
3. [Any additional supporting documents]

Please process my refund request and confirm receipt of this email. I can be reached at {email} for any additional information you may need.

Thank you for your attention to this matter.

Best regards,
{name}
ETS ID: {ets_id}
"""
    return template

def make_phone_call(to_number=TWILIO_TO_NUMBER, from_number=TWILIO_FROM_NUMBER, script=None):
    """Make phone call using curl command"""
    try:
        # Build curl command
        twiml = f'<Response><Say voice="alice" language="en-US">{script}</Say></Response>' if script else ''
        
        curl_command = [
            'curl', '-X', 'POST',
            f'https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Calls.json',
            '--data-urlencode', f'To={to_number}',
            '--data-urlencode', f'From={from_number}',
            '--data-urlencode', f'Twiml={twiml}' if script else 'Url=http://demo.twilio.com/docs/voice.xml',
            '-u', f'{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}'
        ]
        
        # Print curl command (for debugging)
        print("\nExecuting curl command:")
        print(' '.join(curl_command))
        
        # Execute command
        result = subprocess.run(curl_command, capture_output=True, text=True)
        
        # Print complete response (for debugging)
        print("\nAPI Response:")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        
        if result.returncode == 0:
            print("\nPhone call initiated successfully")
            return True
        else:
            print(f"Error making phone call: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"Error making phone call: {str(e)}")
        return None

def generate_call_script(info):
    """Generate phone call script"""
    personal = info.get("personal", {})
    name = f"{personal.get('first_name', '')} {personal.get('last_name', '')}".strip()
    ets_id = personal.get('ets_id', '')
    
    script = f"""
Hello, my name is {name}.
I'm calling about a TOEFL test refund request.
My ETS ID is {ets_id}.
I would like to request a refund for my TOEFL test registration.
"""
    return script

def generate_voice_script(info):
    """Generate voice script"""
    personal = info.get("personal", {})
    name = f"{personal.get('first_name', '')} {personal.get('last_name', '')}".strip()
    ets_id = personal.get('ets_id', '')
    
    script = f"""
Hello, my name is {name}.
I am calling regarding my TOEFL test refund request.
My ETS ID is {ets_id}.

I am calling because I only received a partial refund for my TOEFL test registration.
I kindly request a full refund for the following reasons:

First, I have not taken the test yet.
Second, my registration is still within the refund eligibility period.
Third, I have all the necessary documentation to support my request.

I have already reviewed the ETS refund policy and gathered all required documentation.
I am making this request within the specified timeframe.

I kindly request that you process my full refund according to ETS policies.

Thank you for your attention to my request.
This is {name} with ETS ID {ets_id}.
    """
    return script

if __name__ == "__main__":
    # Set directory paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    personal_dir = os.path.join(script_dir, "personal_info")
    contact_dir = os.path.join(script_dir, "contact_info")
    
    # Create necessary directories
    for directory in [personal_dir, contact_dir]:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")
    
    # Store extracted information
    extracted_info = {}
    
    # Process personal information image
    personal_image = os.path.join(personal_dir, "personal.png")
    if os.path.exists(personal_image):
        text = extract_text_from_image(personal_image)
        if text:
            personal_info = extract_personal_info(text)
            dispute_info = process_dispute(text)
            extracted_info["personal"] = personal_info
            extracted_info["dispute"] = dispute_info
    
    # Process contact information image
    contact_image = os.path.join(contact_dir, "contact.png")
    if os.path.exists(contact_image):
        text = extract_text_from_image(contact_image)
        if text:
            contact_info = extract_contact_info(text)
            extracted_info["contact"] = contact_info
    else:
        print("Warning: No contact information image found")
        extracted_info["contact"] = {
            "contact_email": None,
            "contact_phone": None
        }

    # If no contact phone number found, exit with error
    if ("contact" not in extracted_info or 
        not extracted_info["contact"].get("contact_phone")):
        print("Error: No contact phone number found in the image")
        exit(1)
    
    # Print summary information
    print("\n" + "="*50)
    print("Information Extraction Summary")
    print("="*50)
    
    if "personal" in extracted_info:
        print("\nPersonal Information:")
        for key, value in extracted_info["personal"].items():
            if value:
                print(f"{key}: {value}")
    
    if "contact" in extracted_info:
        print("\nContact Information:")
        for key, value in extracted_info["contact"].items():
            if value:
                print(f"{key}: {value}")
    
    if "dispute" in extracted_info:
        print("\nDispute Analysis:")
        print(f"Primary Category: {extracted_info['dispute']['dispute_category']}")
        print(f"Confidence: {extracted_info['dispute']['confidence']}%")
        print("\nCategory Match Details:")
        for category, count in extracted_info['dispute']['category_details'].items():
            if count > 0:
                print(f"{category}: {count} keyword matches")
    
    # Add template generation after printing summary information
    if "dispute" in extracted_info and extracted_info["dispute"]["dispute_category"] == "ets_refund":
        print("\n" + "="*50)
        print("ETS TOEFL Refund Dispute Template")
        print("="*50)
        template = generate_ets_dispute_template(extracted_info)
        print(template)
        
        # Save template to file
        try:
            with open("ets_dispute_template.txt", "w", encoding="utf-8") as f:
                f.write(template)
            print("\nTemplate saved to ets_dispute_template.txt")
        except Exception as e:
            print(f"Error saving template: {str(e)}")
        
        # Ask if user wants to make a phone call
        print("\n" + "="*50)
        print("Phone Call Option")
        print("="*50)
        
        if "contact" in extracted_info and extracted_info["contact"].get("contact_phone"):
            contact_phone = extracted_info["contact"]["contact_phone"]
            print(f"Detected ETS contact phone: {contact_phone}")
            
            make_call = input("\nWould you like to make a phone call? (y/n): ").lower().strip()
            if make_call == 'y':
                print("\nGenerating voice script...")
                voice_script = generate_voice_script(extracted_info)
                print("\nVoice script content:")
                print(voice_script)
                
                print("\nStarting phone call...")
                call_success = make_phone_call(
                    to_number=os.getenv('TWILIO_TO_NUMBER'),  # Use user-provided number
                    from_number=os.getenv('TWILIO_FROM_NUMBER'),  # Use user's Twilio number
                    script=voice_script
                )
                
                if call_success:
                    print("Phone connected, waiting for automated voice announcement")
                    
                    # Save call history
                    extracted_info["call_history"] = {
                        "timestamp": str(datetime.datetime.now()),
                        "status": "completed",
                        "type": "automated_voice"
                    }
                    save_dispute_info(extracted_info, "complete_analysis.json")
    
    # Save complete information to file
    save_dispute_info(extracted_info, "complete_analysis.json")